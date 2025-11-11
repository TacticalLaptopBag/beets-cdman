# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - Unreleased

### Added

- Added `convert` as a valid value for `audio_populate_mode`. This converts the source file to a variable bitrate MP3 file.
- Added `name` as a valid field for all CDs. This sets the name of the folder to something other than the key.
- Added `path` as a valid field for all CDs. This determines the directory where the CD folder will be placed.
- Added progress percentage to summary
- Empty CDs are now shown to the user after population.
- Add command-line option `--skip-cleanup`
- Add command-line option `--list-empty`

### Changed

- CD definition parsing errors are now shown to the user to help resolve the error


## [1.0.3] - 2025-11-03

### Fixed

- Passing a directory path in `cd_files` or as an argument will now properly search the directory for CD definition files.


## [1.0.2] - 2025-11-02

### Added

- CHANGELOG.md to repository

### Changed

- Split reports will now show folder names in paths for MP3 CDs


## [1.0.1] - 2025-11-01

### Fixed

- Fix periods in folder names causing unstable behavior
- Fix crashing parallel tasks causing `cdman` to hang without feedback


## [1.0.0] - 2025-11-01

Initial release


[1.1.0]: https://github.com/TacticalLaptopBag/beets-cdman/releases/tag/v1.1.0
[1.0.3]: https://github.com/TacticalLaptopBag/beets-cdman/releases/tag/v1.0.3
[1.0.2]: https://github.com/TacticalLaptopBag/beets-cdman/releases/tag/v1.0.2
[1.0.1]: https://github.com/TacticalLaptopBag/beets-cdman/releases/tag/v1.0.1
[1.0.0]: https://github.com/TacticalLaptopBag/beets-cdman/releases/tag/v1.0.0
