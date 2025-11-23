import os
from status_logger import StatusLogger
from colorama import Fore

def verify_status_logger():
    print("Verifying StatusLogger...")
    
    status_file = "test_status.txt"
    if os.path.exists(status_file):
        os.remove(status_file)
        
    StatusLogger.set_status_file(status_file)
    
    test_message = "Test Status Message"
    StatusLogger.print_status(test_message, Fore.GREEN)
    
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            content = f.read()
            if content == test_message:
                print("SUCCESS: Status file written correctly.")
            else:
                print(f"FAILURE: Status file content mismatch. Expected '{test_message}', got '{content}'")
        os.remove(status_file)
    else:
        print("FAILURE: Status file not created.")

if __name__ == "__main__":
    verify_status_logger()
