# beets-cdman
This [beets][beets-docs]
plugin lets you easily manage your collection of CDs.
You can define CDs in your beets config and with
[CD definition files][cd-def-example],
and easily add, remove, or reorder folders.

`cdman` can't burn CDs, but this can be done by other software such as
[Brasero][brasero-page] on GNOME, or [K3b][k3b-page] on KDE.


- [beets-cdman](#beets-cdman)
  - [Install](#install)
  - [Usage](#usage)
  - [MP3 CDs](#mp3-cds)
  - [Audio CDs](#audio-cds)
  - [CD Definition Files](#cd-definition-files)
  - [Credits](#credits)


## Install
Run this in your beets environment:
```bash
pip install beets-cdman
```

Setup your beets config:
```yml
plugins:
  ...
  - cdman

cdman:
  # Path to where you want your CDs to be stored.
  path: ~/Music/CDs  # optional, default ~/Music/CDs

  # The bitrate to use when populating MP3 CDs. This value is in kliobits.
  mp3_bitrate: 192  # optional, default 192

  # How audio CDs should be populated.
  #  - copy: Copy the file from your library to the CD directory
  #  - hard_link: Hard links the file from your library to the CD directory
  #  - soft_link: Soft links the file from your library to the CD directory
  #    - NOTE: Not all filesystems support this
  audio_populate_mode: copy  # optional, defaults to copy

  # How many threads to allocate. Unless you know what you're doing, you should leave this undefined.
  # threads: 12  # optional, default is your hardware thread count

  # This points to CD definitions made in external files
  # Don't use relative paths, as sometimes the system won't be able to find your definitions.
  # You can use `~` to indicate your home directory.
  cd_files:  # optional
    - /path/to/my/cd_file.yml
    - ./dont/use/relative/paths.yml

  # This defines CDs to populate with tracks
  cds:  # optional
    # This will create a CD directory in ~/Music/CDs/mp3-cd-name
    mp3-cd-name:
      # What type of CD this is.
      #  - mp3: An MP3 CD is defined by folders, and converts all tracks to MP3.
      #  - audio: The classic CD standard, simply plops files inside the folder.
      type: mp3

      # You can define the MP3 bitrate to use per-CD if you want.
      # This value overrides your config
      bitrate: 192  # optional, defaults to config

      folders:
        __root__:  # This is a special name that puts tracks inside of this folder directly into the CD folder instead.
          tracks:
            # Tracks can be defined with Beets queries or playlist files
            # There is no limit to the number of query or playlist fields, and they can be intermixed.
            - query: "'artist:Daft Punk'"
            - playlist: "/path/to/playlist_file.m3u"
        foals:
          # You can explicitly define your folder name here.
          # Leaving it undefined simply uses the key used to define this folder,
          # which is `foals` in this case.
          name: "Backwards Foals"  # optional, defaults to folder key
          tracks:
            # Track order matters! This will order the CD so that Part 2 plays before Part 1.
            - query: "'artist:Foals' 'album:Everything Not Saved Will Be Lost, Part 2'"
            - query: "'artist:Foals' 'album:Everything Not Saved Will Be Lost, Part 1'"
```
Note the use of double *and* single quotes.
The double quotes are to ensure YAML doesn't get confused.
The single quotes are to send singular expressions to beets.
For example, `"'artist:Daft Punk' 'album:Discovery'"`
would match all songs in the Discovery album and made by Daft Punk.


## Usage
To create your CDs, simply run
```bash
beet cdman
```
This will look through your beets config for any CDs defined in there.
If any are found, it will then create a folder in your `path`
and place files inside the created folder.

You can also pass in paths to [CD definition files](#cd-definition-files),
or directories containing CD definition files:
```bash
beet cdman daft-punk.yml rock.yml cd-definitions/
```


## MP3 CDs
When `cdman` encounters an MP3 CD definition, it will create folders inside
the CD folder and then convert all music files found from the configured
tracks to an MP3. You can configure the bitrate of these MP3s
with the `mp3_bitrate` config field, changing the `bitrate` field in the CD definition,
or by passing `--bitrate` into the command.

For example, an MP3 CD definition that looks like this:
```yml
discoveries:
  type: mp3
  bitrate: 128
  folders:
    daft-punk:
      name: "Daft Punk"
      tracks:
        - query: "'artist:Daft Punk' 'album:Discovery'"
    Fantom87:
      tracks:
        - query: "'artist:Fantom87' 'album:Discovery'"

the-french-house:
  type: mp3
  bitrate: 256
  folders:
    Joshua:
      tracks:
        - query: "'artist:French79' 'album:Joshua'"
    Teenagers:
      tracks:
        - query: "'artist:French79' 'album:Teenagers'"
```
Would create a directory structure like this:
```
/path/to/cds_path:
    ├── discoveries
    │   ├── 01 Daft Punk
    │   │   ├── 01 One More Time.mp3
    │   │   ├── 02 Aerodynamic.mp3
    │   │   └── ...
    │   └── 02 Fantom87
    │       ├── 01 Pay Phone.mp3
    │       ├── 02 Oh, Dreamer.mp3
    │       └── ...
    └── the-french-house
        ├── 01 Joshua
        │   ├── 01 Remedy.mp3
        │   ├── 02 Hold On.mp3
        │   └── ...
        └── 02 Teenagers
            ├── 01 One for Wendy.mp3
            ├── 02 Burning Legend.mp3
            └── ...
```


## Audio CDs
When `cdman` encounters an Audio CD definition, it will simply populate the CD folder
with all music files found from the configured tracks.
It can either copy, soft link, or hard link the files.
You can configure this behavior with the `audio_populate_mode` config field,
changing the `populate_mode` field in the CD definition, or by passing `--populate-mode`
into the command.

For example, an Audio CD definition that looks like this:
```yml
not-saved-part-1:
  type: audio
  populate_mode: soft_link
  tracks:
    - query: "'artist:Foals' 'album:Everything Not Saved Will Be Lost, Part 1'"

not-saved-part-1:
  type: audio
  populate_mode: copy
  tracks:
    - query: "'artist:Foals' 'album:Everything Not Saved Will Be Lost, Part 2'"
```

Would create a directory structure like this:
```
/path/to/cds_path:
    ├── not-saved-part-1
    │   ├── 01 Moonlight.flac -> /path/to/Moonlight.flac
    │   ├── 02 Exits.flac -> /path/to/Exits.flac
    │   └── ...
    └── not-saved-part-2
        ├── 01 Red Desert.m4a
        ├── 02 The Runner.m4a
        └── ...
```


## CD Definition Files
CD definition files let you define CDs in external files, to help keep your
beets config file less cluttered. CD definition files follow the same format
as the beets config `cds` field.

You can find an example CD definition file [here][cd-def-example]


## Credits
The music files used for testing are all created by [Scott Buckley][scott-buckley],
and is protected under [CC-BY 4.0][cc-by-4.0].


[beets-docs]: https://beets.readthedocs.io/en/latest/index.html
[cd-def-example]: https://github.com/TacticalLaptopBag/beets-cdman/blob/main/example-cdman-definition.yml
[beets-alt-plugin]: https://github.com/geigerzaehler/beets-alternatives/
[brasero-page]: https://wiki.gnome.org/Apps/Brasero/
[k3b-page]: https://apps.kde.org/k3b/
[scott-buckley]: https://www.scottbuckley.com.au/
[cc-by-4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
