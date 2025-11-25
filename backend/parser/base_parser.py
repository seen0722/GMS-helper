from abc import ABC, abstractmethod
from typing import Generator, Dict, Any

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> Generator[Dict[str, Any], None, None]:
        """
        Parses the test result file and yields test case data.
        Should yield a dictionary with keys matching the TestCase model.
        """
        pass

    @abstractmethod
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extracts metadata about the test run (suite name, device info, etc.)
        """
        pass
