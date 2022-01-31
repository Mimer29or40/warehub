# Warehub

A static pypi-like Python repository generator for projects that cannot be hosted on pypi.

## Features

* **Host Anywhere:** Any static file hosting service can be used. This was made with Github Pages in mind.
* **Configurable:** One install can be used to manage multiple repositories.
* **Easy to Use:** Simple give it a Github repository path and warehub will do the rest.

## Get Started

To install, use pip:

```
pip install warehub
```

Generate the config file:

```
python -m warehub init
```

Edit the configuration file: `config.json`

## Configuration

By default, the config file is generated in the current directory.

* `path`: **Required** - The path to the base directory where warehub will write files.
* `database`: **Required** - The path to the database file relative to `path`.
* `url`: **Required** - The url to the website homepage.
* `title`: **Optional** - The title of the website.
    * Default: `Personal Python Package Index`
* `description`: **Optional** - Text to show on the homepage.
    * Default: `Welcome to your private Python package index!`
* `image_url`: **Optional** - The url to an image that will be the favicon and will be displayed on every page
    * Default: `https://pypi.org/static/images/logo-small.95de8436.svg`

## Usage

    python -m warehub init [options]
    python -m warehub add [(--username USERNAME --password PASSWORD)] [--domain DOMAIN] [--no-generate] repositories [options]
    python -m warehub generate [options]
    
    Commands:
        init
            Generate required files and directories.
        add
            Add the relases to the database from the provided github
            repositories.
        generate
            Generate the webpage files used to emulate a pypi-like interface
    
    Options:
        -v --verbose
            Show Verbose Output
        -c CONFIG --config CONFIG
            The path to the config file. [default: ./config.json]
        
        -u USERNAME --username USERNAME
            The username to authenticate to the repository (package index) as.
            (Can also be set via WAREHUB_USERNAME environment variable.)
            [default: WAREHUB_USERNAME|None]
        -p PASSWORD --password PASSWORD
            The password to authenticate to the repository (package index) as.
            (Can also be set via WAREHUB_PASSWORD environment variable.)
            [default: WAREHUB_PASSWORD|None]
        -d DOMAIN --domain DOMAIN
            The domain to access the Github api from. This will only change for
            Github Enterprise users. [default: https://api.github.com/]
        --no-generate
            Skips the generation of the file structure
        repositories
            The Github repository paths to upload to the index. Usually in the
            form <user>/<repo_name>.

### Note: Username and Passwords

It is bad practice to supply username's and password's in plain text especially when hosted on a public platform.

To prevent this vulnerability, warehub can pull this information from the environment variables `WAREHUB_USERNAME` and `WAREHUB_PASSWORD`. This is the recommended way to provide a
username and password.

The username and password environment variables can be over written by passed in these values to as arguments. This should only be used for one off runs and not as saved run
configurations.

## FAQ

#### Q. Is it secure?

It depends on your hosting solution. If you use a public website hosting service such as Github Pages, then packages uploaded will be public regardless if the providing repository
is private.

#### Q. What happen behind the scenes?

When running `pip install <package_name> --extra-index-url <repo_url>`, the following happen:

1. `pip` will look at `https://pypi.org/`, the default, public index, trying to find a package with the specified name.
2. If it can't find, it will look at `<repo_url>`.
3. If the package is found there, the link of the package is returned to `pip <repo_link>`.
4. `pip` install any missing dependency with the same steps.

#### Q. What if the name of my package is already taken by a package in the public index?

You can just specify a different name for your indexed package. Just give it a different name in the form when registering it.

For example if you have a private package named `tensorflow`, when you register it in this index, you can name it `my_cool_tensorflow`, so there is no name-collision with the
public package `tensorflow`.  
Then you can install it with `pip install my_cool_tensorflow --extra-index-url <repo_url>`.

Then from `python`, you can just do:

```python
import tensorflow
```

_Note: While it's possible to do like this, it's better to have a unique name for your package, to avoid confusion._

#### Q. How to add this repository to IDE's (PyCharm, etc)?

To add this repository to an IDE, simply add `<repo_url>/simple` to the list of repositories. This mirrors the api of pypi so it should work as long as your IDE supports pypi.

---

**_If you have any questions or ideas to improve this FAQ, please open a PR / blank issue!_**

## Contribute

Issues and PR are welcome!

If you come across anything weird / that can be improved, please get in touch!

## References

**This is greatly inspired from [this repository](https://github.com/ceddlyburge/python-package-server).**  
It's just a glorified version, with cleaner pages and github actions for easily adding, updating and removing packages from your index.

Also check the [blogpost](https://www.freecodecamp.org/news/how-to-use-github-as-a-pypi-server-1c3b0d07db2/) of the original author!

Another reference use were the official pypi software, twine and warehouse. They were used to make sure that all the required information was inputted.
