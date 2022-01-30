from pathlib import Path


def main():
    test_data_dir: Path = Path('test_data')

    data_file = test_data_dir / 'data.json'
    data_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
