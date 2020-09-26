# typing_copilot

Helper for starting to type-hint large codebases with `mypy`. When installed, available as the command `typing_copilot`.

Example output generated when generating a `mypy.ini` file for the [GraphQL compiler](https://github.com/kensho-technologies/graphql-compiler) project ([PR link](https://github.com/kensho-technologies/graphql-compiler/pull/876)):
```bash
# First, enter the project's virtual environment.
# Make sure the project's dependencies are installed in the environment!
$ poetry shell  # or "pipenv shell" or "source venv/bin/activate" or ...
<...>

$ typing_copilot init
typing_copilot v0.4.0

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

`typing_copilot` aims to make this process extremely quick and simple. After installing this package in your project's development environment, running `typing_copilot init` will autogenerate a `mypy.ini` file with the strictest set of `mypy` rules that your code currently passes. In future runs, `mypy` will automatically use the new `mypy.ini` file, thereby ensuring that no future code edits violate any typing rules that the current codebase satisfies.

You can then also use the `mypy.ini` file to see which checks had to be disabled for which of your project's modules, and use that information to guide your future typing efforts. You can also periodically re-run `typing_copilot tighten` to regenerate a `mypy.ini` file, in case your project's typing state has improved and stricter rules may now be adopted.

Ideally, consider using `typing_copilot` in a "ratcheting" fashion, where your project is always on the tightest possible `mypy.ini` configuration. The easiest way to do so is to run `typing_copilot tighten --error-if-can-tighten` in your CI environment, which will `exit 1` in case your current `mypy.ini` is not the tightest possible one for your project.

In the future, we hope to add additional functionality to `typing_copilot`:
- a command that highlights opportunities where a small amount of work can allow a new rule to be enabled for a new module, allowing you to maximize your project's typing enforcement;
- support for additional `mypy` rules.

## Usage

1. Navigate to the root directory of the project on which you'd like to use `typing_copilot`.
2. Enter the project's virtualenv, if using one, and ensure the project's dependencies are installed.
3. Run `typing_copilot`:
```bash
pip install typing_copilot

typing_copilot init
```

Currently, `typing_copilot` is unable to support `mypy.ini` files that it did not generate. If you are already using `mypy` but you'd like to transition to using `typing_copilot` to manage your `mypy.ini` file, you can make use of the `--overwrite` flag:
```bash
typing_copilot init --overwrite
```

After creating your initial `mypy.ini` file with `typing_copilot`, you can also use `typing_copilot` to attempt to tighten your `mypy.ini` configuration. This is useful, for example, if you've recently added type hints to your code and believe that should enable a tighter new `mypy.ini` configuration. Simply run the following to update your `mypy.ini` to the tightest passing `mypy` configuration:
```bash
typing_copilot tighten
```

In a CI environment, `typing_copilot` can simultaneously ensure both that your code passes `mypy` checks with the current `mypy.ini` configuration, and that the current `mypy.ini` file is the tightest `mypy` config that your code is able to support. Simply use the `--error-if-can-tighten` flag in the `tighten` command:
```bash
typing_copilot tighten --error-if-can-tighten
```

## How `typing_copilot` works

### `typing_copilot init`

With this command, `typing_copilot` will first run `mypy` using a minimal set of `mypy` checks which are always enabled and cannot be turned off. You'll need to fix any errors `mypy` finds using these checks before the command will be able to proceed.

Once the minimal `mypy` checks pass, `typing_copilot init` will automatically re-run `mypy` with the strictest supported set of checks, and collect the reported errors. After analyzing the errors, it will generate the strictest set of checks that will not cause errors, validate them by running `mypy` against your project one more time, and then create a new `mypy.ini` file with this new "strictest valid" configuration. We generally refer to this "strictest valid" configuration as the project's "tightest" configuration, hence the `tighten` command described below.

### `typing_copilot tighten`

With this command, `typing_copilot` will first run `mypy` using your current `mypy.ini` file, ensuring that the current configuration does not produce any `mypy` errors. Assuming no errors are found, `typing_copilot` will then follow the same procedure as in the `init` command to find the tightest `mypy` configuration your project's current state supports. Finally, it will compare this newly-found tightest configuration against your current `mypy.ini` configuration, and either update your `mypy.ini` file or return an error, depending on whether the `--error-if-can-tighten` is set.

## Reporting issues

This is a project I built in my spare time, please be gentle :)

GitHub issues are the preferred avenue for reporting issues with `typing_copilot`. Please do not email me or any other contributors with questions or issue reports, unless you have our explicit consent to do so.

To ensure the best odds that we can diagnose and fix any problems together, please make sure to include in your issue report the log produced using the `--verbose` option, together with links to the source code being analyzed by `mypy` and `typing_copilot`.

As always, pull requests highly encouraged and gratefully accepted.
