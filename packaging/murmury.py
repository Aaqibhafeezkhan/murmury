"""Entry point of the packaged app (Murmury.app)."""
import multiprocessing

if __name__ == "__main__":
    # a frozen app is also started as multiprocessing's helper (the resource tracker the speech model's
    # downloads use): this runs the helper and exits, instead of starting a second Murmury
    multiprocessing.freeze_support()
    from copilot.app import main
    main()
