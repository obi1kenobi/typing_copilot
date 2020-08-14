# typing-copilot

Helper for starting to type-hint large codebases with `mypy`. When installed, available as the command `tc`.

Example output generated when generating a `mypy.ini` file for the [GraphQL compiler](https://github.com/kensho-technologies/graphql-compiler) project ([PR link](https://github.com/kensho-technologies/graphql-compiler/pull/876)):
```bash
# First, enter the project's virtual environment.
# Make sure the project's dependencies are installed in the environment!
$ pipenv shell
<...>

$ tc init
typing_copilot v0.2.0

Running mypy once with laxest settings to establish a baseline. Please wait...

Collecting mypy errors from strictest check configuration. Please wait...

Strict run completed and uncovered 2955 mypy errors. Building the strictest mypy config
such that all configured mypy checks still pass...

> Mypy was unable to find type hints for some 3rd party modules, configuring mypy to
ignore them.
    More info: https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
    Affected modules: ['arrow', 'cached_property', 'funcy', 'neo4j', 'parameterized',
        'pyorient', 'pytest', 'redisgraph', 'setuptools', 'snapshottest', 'sqlalchemy']

> Constructed 126 mypy error suppression rules across 65 modules.

Config generated (306 lines). Validating the new setup before updating your mypy.ini
file. Please wait...

Validation complete. Your mypy.ini file has been updated. Happy type-safe coding!
```

## Motivation

Starting to use `mypy` in a large codebase can feel like a chicken-and-egg problem:
- You are unable to turn on meaningful `mypy` enforcement since a large portion of the codebase is not compliant.
- It is difficult to get the codebase compliant without `mypy` enforcement: since proper typing is not enforced, even brand-new code is frequently not fully compliant, and it feels like you are making one step forward and two steps back.

`mypy` allows specifying different levels of rule enforcement on a per-module basis. However, writing a good per-module `mypy` configuration is an extremely time-consuming process: `mypy` must be executed (in a strict configuration) against that module, the resulting errors must be triaged, and an appropriate set of rules for the modules must be produced. Applying this process on a large codebase can easily take hours or days of work.

`typing-copilot` aims to make this process extremely quick and simple. After installing this package in your project's development environment, running `tc init` will autogenerate a `mypy.ini` file with the strictest set of `mypy` rules that your code currently passes. In future runs, `mypy` will automatically use the new `mypy.ini` file, thereby ensuring that no future code edits violate any typing rules that the current codebase satisfies.

You can then also use the `mypy.ini` file to see which checks had to be disabled for which of your project's modules, and use that information to guide your future typing efforts. You can also periodically re-run `tc init --overwrite` to regenerate a `mypy.ini` file, in case your project's typing state has improved and stricter rules may now be adopted.

In the future, we hope to add additional functionality to `typing-copilot`:
- a command that highlights opportunities where a small amount of work can allow a new rule to be enabled for a new module, allowing you to maximize your project's typing enforcement;
- support for additional `mypy` rules.

## Usage

1. Navigate to the root directory of the project on which you'd like to use `typing-copilot`.
2. Enter the project's virtualenv, if using one, and ensure the project's dependencies are installed.
3. Run `typing-copilot`:
```bash
pip install typing-copilot

tc init
```

If you are already using `mypy` for your project and already have a `mypy.ini` file that you would like to overwrite, simply add the `--overwrite` option:
```bash
tc init --overwrite
```

`typing-copilot` will first run `mypy` using a minimal set of `mypy` checks which are always enabled and cannot be turned off. You'll need to fix any errors `mypy` finds using these checks before moving to the next step.

Once the minimal `mypy` checks pass, `tc init` will automatically re-run `mypy` with the strictest supported set of checks, and collect the reported errors. After analyzing the errors, it will generate the strictest set of checks that will not cause errors, validate them by running `mypy` against your project one more time, and then create a new `mypy.ini` file with this new "strictest valid" configuration.

## Reporting issues

This is a project I built in my spare time, please be gentle :)

GitHub issues are the preferred avenue for reporting issues with `typing-copilot`. Please do not email me or any other contributors with questions or issue reports, unless you have our explicit consent to do so.

To ensure the best odds that we can diagnose and fix any problems together, please make sure to include in your issue report the log produced using the `--verbose` option, together with links to the source code being analyzed by `mypy` and `typing-copilot`.

As always, pull requests highly encouraged and gratefully accepted.
