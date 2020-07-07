import click


_verbose_mode = False


def enable_verbose_mode() -> None:
    global _verbose_mode
    _verbose_mode = True


def disable_verbose_mode() -> None:
    global _verbose_mode
    _verbose_mode = False


def log_if_verbose(message: str) -> None:
    if _verbose_mode:
        click.echo(message, err=True)
