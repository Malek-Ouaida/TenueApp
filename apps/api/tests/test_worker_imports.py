import importlib


def test_closet_worker_runner_imports_without_circular_dependency() -> None:
    worker_runner = importlib.import_module("app.domains.closet.worker_runner")

    assert callable(worker_runner.run_once)


def test_wear_worker_runner_imports_without_circular_dependency() -> None:
    worker_runner = importlib.import_module("app.domains.wear.worker_runner")

    assert callable(worker_runner.run_once)
