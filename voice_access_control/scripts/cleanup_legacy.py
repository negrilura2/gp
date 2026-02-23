import os
import sys

def cleanup():
    # Candidates for removal
    # These files are likely superseded by the new architecture
    candidates = [
        "scripts/audio/record_and_verify.py",
        "scripts/audio/record_audio.py",
        "scripts/data/reorganize_vox.py", # If not needed anymore
        "scripts/evaluate.py", # Might still be useful for offline eval, check before deleting
        "model/infer.py",
        "model/verify_demo.py",
        "model/enroll.py",
        "model/train.py", # If training is moved to voice_engine/trainer.py
        # Add more here
    ]
    
    print("The following files are candidates for removal:")
    for f in candidates:
        if os.path.exists(f):
            print(f" - {f}")
        else:
            print(f" - {f} (Already gone)")
            
    print("\nNote: Please verify manually before confirming deletion.")
    print("This script is a placeholder. Modify the 'candidates' list and uncomment the deletion logic to proceed.")

    # Uncomment to enable deletion
    # confirm = input("\nAre you sure you want to delete these files? (y/n): ")
    # if confirm.lower() == 'y':
    #     for f in candidates:
    #         if os.path.exists(f):
    #             os.remove(f)
    #             print(f"Deleted {f}")
    # else:
    #     print("Aborted.")

if __name__ == "__main__":
    cleanup()
