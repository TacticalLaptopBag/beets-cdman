# beets-cdman
This [beets][beets-docs]
plugin lets you easily manage your collection of CDs.
You can define MP3 CDs in your beets config or with a
[CD definition file][cd-def-example],
and easily add, remove, or reorder folders.


- [beets-cdman](#beets-cdman)
  - [Install](#install)
  - [Usage](#usage)
  - [MP3 CDs](#mp3-cds)
  - [CD Definition Files](#cd-definition-files)


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
  # Path to where your CDs will be stored
  cds_path: ~/Music/CDs
  # The bitrate, in kbps, to use for MP3 CDs
  bitrate: 128
  cds:
    cd-name:
      - name: Folder 1
        query: "'artist:Daft Punk'"
      - name: Second Folder
        query: "'artist:The Black Keys'"
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
If any are found, it will then create a folder in your `cds_path`
and place files inside the created folder.

You can also pass in paths to [CD definition files](#cd-definition-files),
or directories containing CD definition files:
```bash
beet cdman daft-punk.yml cd-definitions/ rock.yml
```


## MP3 CDs
Currently, `cdman` only creates MP3 CDs, but support for Audio CDs is planned.
For the time being, [beets-alternatives][beets-alt-plugin]

When `cdman` encounters an MP3 CD definition, it will create folders inside
the CD folder and then convert all music files found from the configured
beets query to an MP3. You can configure the bitrate of these MP3s
with the `bitrate` config field, or by passing `--bitrate` into the command.

For example, an MP3 CD definition that looks like this:
```yml
discoveries:
  - name: Daft Punk
    query: "'artist:Daft Punk' 'album:Discovery'"
  - name: Fantom87
    query: "'artist:Fantom87' 'album:Discovery'"
the-french-house:
  - name: Joshua
    query: "'artist:French79' 'album:Joshua'"
  - name: Teenagers
    query: "'artist:French79' 'album:Teenagers'"
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


## CD Definition Files
CD definition files let you define CDs in external files, to help keep your
beets config file less cluttered. CD definition files follow the same format
as the beets config `cds` field.

You can find an example CD definition file [here][cd-def-example]

[beets-docs]: https://beets.readthedocs.io/en/latest/index.html
[cd-def-example]: https://github.com/TacticalLaptopBag/beets-cdman/blob/main/example-cdman-definition.yml
[beets-alt-plugin]: https://github.com/geigerzaehler/beets-alternatives/
