import os

def init_dirs():
    dirs = ["directives", "execution", ".tmp", "backend", "frontend"]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"Created directory: {d}")
        else:
            print(f"Directory already exists: {d}")

if __name__ == "__main__":
    init_dirs()
