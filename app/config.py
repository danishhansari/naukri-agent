from dataclasses import dataclass


@dataclass(frozen=True)
class JobSearchConfig:
    keyword: str = "Java Developer"
    min_experience: int = 1
    max_experience: int = 6

    # We only want applications that stay on Naukri.
    naukri_only: bool = True

    # Number of jobs to consider in one run.
    max_jobs_per_run: int = 50