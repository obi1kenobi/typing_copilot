# typing-copilot

Helper for starting to type-hint large codebases with `mypy`. When installed, available as the command `tc`.

Example output generated when generating a `mypy.ini` file for the [GraphQL compiler](https://github.com/kensho-technologies/graphql-compiler) project ([PR link](https://github.com/kensho-technologies/graphql-compiler/pull/876)):
```
$ tc init
typing_copilot v0.1.0

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
