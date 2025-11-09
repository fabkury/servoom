"""Smoke tests for servoom package."""

from pathlib import Path

from servoom import PixelBeanDecoder, DivoomClient
from servoom.config import Config


def decode_dat_folder(folder: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    for dat_file in sorted(folder.glob('*.dat')):
        bean = PixelBeanDecoder.decode_file(str(dat_file))
        out_path = output / (dat_file.stem + '.webp')
        bean.save_to_webp(str(out_path))
        print(f"Decoded {dat_file.name} -> {out_path}")


def main():
    from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD

    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    client.login()

    mixed_dir = Path('reference-animations/mixed/DAT')
    out_dir = Path('decoded-mixed-clean')
    decode_dat_folder(mixed_dir, out_dir)


if __name__ == '__main__':
    main()
