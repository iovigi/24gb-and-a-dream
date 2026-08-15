from pathlib import Path

from core.project import VideoProject
from core.requests import GenerationRequest
from llm.mock import MockLLMEngine


def test_project_directory_and_scene_state_persistence(tmp_path: Path) -> None:
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    request = GenerationRequest(prompt="Castle storm", reference_image=image)
    project = VideoProject.create(request, tmp_path / "projects")
    project.director_plan = MockLLMEngine().create_director_plan(request)
    project.initialize_scenes()
    output = project.scene_output(1)
    output.write_bytes(b"video")
    project.set_scene_status(1, "completed")
    loaded = VideoProject.load(project.project_directory)
    assert loaded.reference_image.is_file()
    assert loaded.has_valid_scene_output(1)
    assert (loaded.project_directory / "director_plan.json").is_file()
