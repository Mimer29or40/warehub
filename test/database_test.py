from pathlib import Path
from pprint import pprint

from warehub.database import Database
from warehub.model import Project


def main():
    Database.file(Path('test/data.json'))
    
    # project = Project('Test')
    # Database.put(Project, project)
    
    projects = Database.get(Project, where=Project.name == 'Test1')
    if len(projects) > 0:
        projects[0].name = 'RENAMED'
    
    pprint(Database._data)
    
    # projects = Database.get(Project)
    # pprint(projects)
    #
    # Database.commit()


if __name__ == '__main__':
    main()
