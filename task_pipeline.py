"""Task Pipeline module for sequential and parallel stage execution."""

import concurrent.futures
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskPipeline:
    """A pipeline that executes stages sequentially, with optional parallel groups.

    Stages are added via :meth:`add_stage` and can optionally be grouped for
    parallel execution via :meth:`set_parallel`.  When :meth:`run` is called,
    every parallel group fires concurrently (using a
    :class:`concurrent.futures.ThreadPoolExecutor`), while the groups
    themselves execute in the order the individual stages were registered.
    """

    def __init__(self):
        """Initialize an empty :class:`TaskPipeline`."""
        self._stages: list[tuple[str, callable]] = []
        self._parallel_groups: set[str] = set()

    def add_stage(self, name: str, func: callable) -> None:
        """Add a processing stage to the pipeline.

        Args:
            name: A unique string identifier for this stage.
            func: A callable that accepts a single data argument and
                  returns the transformed data.

        Raises:
            ValueError: If a stage with the same *name* already exists.
        """
        if any(s[0] == name for s in self._stages):
            raise ValueError(f"Stage '{name}' already exists.")
        self._stages.append((name, func))

    def set_parallel(self, stages: list[str]) -> None:
        """Mark a group of stages for parallel execution.

        All stages listed in *stages* will be executed concurrently as a
        single group.  Stages not listed here run sequentially in the
        order they were added.

        Args:
            stages: An iterable of stage names to execute in parallel.

        Raises:
            ValueError: If any listed name was not previously registered.
        """
        for name in stages:
            if not any(s[0] == name for s in self._stages):
                raise ValueError(f"Stage '{name}' is not registered.")
            self._parallel_groups.add(name)

    def run(self, data) -> any:
        """Execute the pipeline on the given input data.

        Stages are grouped into sequential blocks.  Within each block,
        parallel stages run concurrently; blocks themselves execute in
        the order the stages were originally added.

        Args:
            data: The input data passed to the first stage.

        Returns:
            The final data after all stages have completed.
        """
        groups = self._build_groups()
        logger.info("Pipeline started with %d group(s)", len(groups))

        for group in groups:
            if len(group) == 1:
                name, func = group[0]
                logger.info("Running stage: %s", name)
                data = func(data)
            else:
                logger.info("Running parallel group: %s",
                            ", ".join(s[0] for s in group))
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(func, data): name
                        for name, func in group
                    }
                    for future in concurrent.futures.as_completed(futures):
                        future.result()  # wait for completion; data updated in place
            logger.info("Stage complete")

        logger.info("Pipeline finished")
        return data

    def _build_groups(self) -> list[list[tuple[str, callable]]]:
        """Build sequential execution groups from registered stages.

        Returns:
            A list of lists, where each inner list contains the stage
            (name, func) tuples for one execution group.
        """
        groups: list[list[tuple[str, callable]]] = []
        current_group: list[tuple[str, callable]] = []

        for stage in self._stages:
            if stage[0] in self._parallel_groups:
                current_group.append(stage)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([stage])

        if current_group:
            groups.append(current_group)

        return groups


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------

def _load_config(data: dict) -> dict:
    """Stage 1 - Load configuration from a string path.

    Args:
        data: Dict with a ``config_path`` key.

    Returns:
        The data dict updated with a ``config`` key.
    """
    path = data.get("config_path", "default.cfg")
    data["config"] = f"loaded:{path}"
    logger.info("Config loaded from %s", path)
    return data


def _validate_data(data: dict) -> dict:
    """Stage 2 - Validate the input data structure.

    Args:
        data: A dictionary to validate.

    Returns:
        The validated data dict with a ``valid`` key.
    """
    data["valid"] = all(k in data for k in ("config",))
    logger.info("Validation result: %s", data["valid"])
    return data


def _fetch_remote(data: dict) -> dict:
    """Stage 3a (parallel) - Simulate a remote API fetch.

    Args:
        data: A dictionary.

    Returns:
        A dict with a ``remote_data`` key.
    """
    time.sleep(0.1)
    data["remote_data"] = {"status": "ok", "records": 42}
    logger.info("Remote fetch complete")
    return data


def _fetch_database(data: dict) -> dict:
    """Stage 3b (parallel) - Simulate a database query.

    Args:
        data: A dictionary.

    Returns:
        A dict with a ``db_data`` key.
    """
    time.sleep(0.1)
    data["db_data"] = {"status": "ok", "records": 100}
    logger.info("Database query complete")
    return data


def _aggregate(data: dict) -> dict:
    """Stage 4 - Aggregate results from all sources.

    Args:
        data: A dictionary containing ``remote_data`` and ``db_data``.

    Returns:
        The data dict updated with an ``aggregate`` key.
    """
    remote = data.get("remote_data", {})
    db = data.get("db_data", {})
    data["aggregate"] = {
        "total_records": remote.get("records", 0) + db.get("records", 0),
    }
    logger.info("Aggregated %d records", data["aggregate"]["total_records"])
    return data


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Build and run a 5-stage pipeline with parallel execution.

    Stages 3 and 4 (*fetch_remote*, *fetch_database*) run in parallel;
    the remaining stages run sequentially.
    """
    pipeline = TaskPipeline()

    pipeline.add_stage("load_config", _load_config)
    pipeline.add_stage("validate_data", _validate_data)
    pipeline.add_stage("fetch_remote", _fetch_remote)
    pipeline.add_stage("fetch_database", _fetch_database)
    pipeline.add_stage("aggregate", _aggregate)

    # Stages 3 and 4 run in parallel
    pipeline.set_parallel(["fetch_remote", "fetch_database"])

    initial_data = {"config_path": "production.cfg"}

    result = pipeline.run(initial_data)

    print("\n--- Pipeline Result ---")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
