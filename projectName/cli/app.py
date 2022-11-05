import shutil

import typer

terminal_width = shutil.get_terminal_size((80, 20))[0]
main_app = typer.Typer(context_settings={'max_content_width': terminal_width})

if __name__ == '__main__':
    main_app()
