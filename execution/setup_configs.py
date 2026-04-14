import os

def setup_configs():
    # env
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("DEBUG=True\nSECRET_KEY=your-secret-key-here\nDATABASE_URL=sqlite:///db.sqlite3\n")
        print("Created .env")

    # gitignore
    if not os.path.exists(".gitignore"):
        with open(".gitignore", "w") as f:
            f.write("node_modules/\nvenv/\n.tmp/\n*.sqlite3\n.env\n__pycache__/\n")
        print("Created .gitignore")

    # requirements.txt
    if not os.path.exists("requirements.txt"):
        with open("requirements.txt", "w") as f:
            f.write("asgiref==3.8.1\nDjango==5.1\ndjango-cors-headers==4.7.0\ndjangorestframework==3.16.0\npython-decouple==3.8\n")
        print("Created requirements.txt")

if __name__ == "__main__":
    setup_configs()
