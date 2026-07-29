from app.projects.schema import ProjectUpdate


def test_project_update_allows_normalized_website_url():
    update = ProjectUpdate(website_url="https://www.Example.com/path")

    assert update.website_url == "example.com"
