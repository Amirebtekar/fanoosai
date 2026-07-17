import json
import uuid
from dataclasses import asdict, dataclass
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import settings


@dataclass(frozen=True)
class PromptRunJob:
    prompt_id: int
    ai_model_id: int
    run_date: str
    attempts: int = 0


class PromptRunQueue:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.stream = settings.REDIS_QUEUE_NAME
        self.group = settings.REDIS_QUEUE_GROUP
        self.consumer = f"worker-{uuid.uuid4().hex}"

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue_once(self, job: PromptRunJob) -> bool:
        """Enqueue once per prompt/model/day using an atomic Redis script."""
        dedupe_key = f"{self.stream}:scheduled:{job.prompt_id}:{job.ai_model_id}:{job.run_date}"
        payload = json.dumps(asdict(job), separators=(",", ":"))
        script = """
        if redis.call('SET', KEYS[1], '1', 'EX', ARGV[2], 'NX') then
            redis.call('XADD', KEYS[2], '*', 'payload', ARGV[1])
            return 1
        end
        return 0
        """
        return bool(await self.redis.eval(script, 2, dedupe_key, self.stream, payload, 172800))

    async def enqueue_retry(self, job: PromptRunJob) -> None:
        await self.redis.xadd(self.stream, {"payload": json.dumps(asdict(job), separators=(",", ":"))})

    async def acquire_scheduler_lock(self) -> str | None:
        token = uuid.uuid4().hex
        acquired = await self.redis.set(
            f"{self.stream}:scheduler-lock",
            token,
            ex=max(settings.AUTOMATIC_RUN_INTERVAL_SECONDS - 5, 10),
            nx=True,
        )
        return token if acquired else None

    async def release_scheduler_lock(self, token: str) -> None:
        await self.redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            1,
            f"{self.stream}:scheduler-lock",
            token,
        )

    async def read(self, block_seconds: int = 5) -> list[tuple[str, PromptRunJob]]:
        await self.ensure_group()
        reclaimed = await self.redis.xautoclaim(
            self.stream, self.group, self.consumer, min_idle_time=60000, start_id="0", count=1
        )
        if len(reclaimed) >= 2 and reclaimed[1]:
            return [
                (entry_id, PromptRunJob(**json.loads(fields["payload"])))
                for entry_id, fields in reclaimed[1]
            ]
        rows = await self.redis.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: ">"},
            count=1,
            block=block_seconds * 1000,
        )
        jobs = []
        for _, entries in rows or []:
            for entry_id, fields in entries:
                jobs.append((entry_id, PromptRunJob(**json.loads(fields["payload"]))))
        return jobs

    async def ack(self, entry_id: str) -> None:
        await self.redis.xack(self.stream, self.group, entry_id)
