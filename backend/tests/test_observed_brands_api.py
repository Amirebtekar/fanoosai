from app.projects.router import router
from app.projects.schema import ObservedBrandRead


def test_observed_brands_endpoint_has_a_typed_response():
    routes = {(next(iter(route.methods)), route.path): route.response_model for route in router.routes}

    assert routes[("GET", "/projects/{project_id}/observed-brands")] == list[ObservedBrandRead]
    assert set(ObservedBrandRead.model_fields) == {"brand_id", "name", "domain"}
