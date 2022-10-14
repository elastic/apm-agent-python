class ExistingFailedJobs(Exception):
    """Exception raised for errors with the Kubernetes Jobs.

    Attributes:
        jobs -- list of failed jobs
        message -- explanation of the error
    """

    def __init__(self, jobs, message="There are failed jobs"):
        self.jobs = jobs
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}\n {self.jobs}"
