from config import SETTINGS


def main() -> None:
    print("OCI Inventory starting...")
    print(f"Configured profile: {SETTINGS.get('profile', 'default')}")


if __name__ == "__main__":
    main()
