from app.projects.schema import ProjectRead


def test_project_read_includes_website_url():
    assert "website_url" in ProjectRead.model_fields
