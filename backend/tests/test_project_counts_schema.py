from app.projects.schema import ProjectRead


def test_project_read_includes_prompt_and_model_counts():
    assert "prompt_count" in ProjectRead.model_fields
    assert "model_count" in ProjectRead.model_fields
