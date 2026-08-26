'''
This file is for the main cli of the program. 

Current cli implementation:
As according to sprint 1 w2; The cli lets users input address and from calls all the different fetchers and returns 1 json file containing all accepted results
'''
# todo: Implement simple user input for text (string)
# todo: Implement fetchers to be called upon 
# todo: Each successful result of the fetcher should be passed into a single json file
# todo: Each fetcher should show pass or fail on the screen 

def print_banner():
    banner = r"""
   _____ _           _        _____                     _
  / ____| |         (_)      / ____|                   | |
 | |    | |__   __ _ _ _ __ | |  __ _   _  __ _ _ __ __| |
 | |    | '_ \ / _` | | '_ \| | |_ | | | |/ _` | '__/ _` |
 | |____| | | | (_| | | | | | |__| | |_| | (_| | | | (_| |
  \_____|_| |_|\__,_|_|_| |_|\_____|\__,_|\__,_|_|  \__,_|

        Blockchain Security Assistant
"""
    print(banner)


if __name__ == "__main__":
    print_banner()

