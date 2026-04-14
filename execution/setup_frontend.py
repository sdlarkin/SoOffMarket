import subprocess
import os

def setup_frontend():
    frontend_dir = "frontend"
    if not os.path.exists(frontend_dir):
        os.makedirs(frontend_dir)
    if not os.path.exists(os.path.join(frontend_dir, "package.json")):
        print("Initializing Next.js frontend...")
        # Note: In a real scenario, this might be interactive. We use flags to keep it non-interactive.
        subprocess.run([
            "npx", "-y", "create-next-app@latest", ".", 
            "--ts", "--tailwind", "--eslint", "--app", "--src-dir=false", "--import-alias=@/*", "--no-git"
        ], cwd=frontend_dir, check=True, shell=True)
        
        print("Installing additional dependencies...")
        subprocess.run([
            "npm", "install", "lucide-react", "framer-motion", "sonner", 
            "@radix-ui/react-slot", "class-variance-authority", "uuid"
        ], cwd=frontend_dir, check=True, shell=True)
    else:
        print("Frontend already initialized.")

if __name__ == "__main__":
    setup_frontend()
