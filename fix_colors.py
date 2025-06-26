import os, sys, subprocess, platform
def fix():
    print(' Tiz Lion AI Agent - Color Fixer')
    print('Installing colorama and rich...')
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'colorama', 'rich', '--upgrade'])
        print(' Libraries installed')
    except: print(' Install failed')
    
    try:
        from colorama import init, Fore, Style
        init(autoreset=True)
        print(f'{Fore.GREEN} Colors working!{Style.RESET_ALL}')
    except: print(' Colors failed')
    
    try:
        from rich.console import Console
        Console().print('[green] Rich working![/green]')
    except: print(' Rich failed')
    
    print(' Tiz Lion AI Agent ready!')

if __name__ == '__main__': fix()
