import unittest

import warehub


class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertIsNotNone(warehub.__metadata_version__, "Metadata Version is None")
        self.assertIsNotNone(warehub.__title__, "Package Name is None")
        self.assertIsNotNone(warehub.__version__, "Package Version is None")
        self.assertIsNotNone(warehub.__summary__, "Package Summary is None")
        self.assertIsNotNone(warehub.__author__, "Package Author is None")
        self.assertIsNotNone(warehub.__maintainer__, "Package Maintainer is None")
        self.assertIsNotNone(warehub.__license__, "Package License is None")
        self.assertIsNotNone(warehub.__url__, "Package URL is None")
        self.assertIsNotNone(warehub.__download_url__, "Package Download URL is None")
        # self.assertIsNotNone(warehub.__project_urls__, "Package Version is None")
        # self.assertIsNotNone(warehub.__copyright__, "Package Version is None")
        # self.assertIsNotNone(warehub.__data_dir__, "Package Version is None")


if __name__ == "__main__":
    unittest.main()
