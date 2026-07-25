from app.projects.schema import ProjectUpdate


def test_project_update_does_not_allow_website_url():
    assert "website_url" not in ProjectUpdate.model_fields
