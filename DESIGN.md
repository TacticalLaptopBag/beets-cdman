# Design Document

## Definitions

### CD Path
The path where all populated CDs are stored

### Populated CD
A directory tree that represents a CD.
This contains audio files that can then be directly placed into a CD.

### Numbered
Whether a track file matches the regex `^0*\d+\s+`

## Requirements
1. Must use the beets config file to read CD data.
2. The config file can point to other YAML files that define CDs.
3. The CLI may take arguments that point to YAML files that define CDs.
4. Users must be able to define MP3 and Audio CDs alike.
5. Audio CDs may be populated with soft links, hard links, or file copies, depending on user or CD config.
6. CD config must always override user config.
7. CD definition files may point to m3u files instead of beets queries.
8. MP3 CDs are defined in folders. Defining a folder named `__root__` will place tracks directly into the CD, rather than into a folder.
9. Audio CDs are defined as tracks, and may be a list of beets queries and m3u playlists.
10. Tracks must be placed into CDs with a track number system. E.g. they must start with 01, 02, etc.
  - If there are more than 99 tracks, they must start with 001, 002, etc.
11. CD definitions must conform to the following syntax:
```yml
# MP3 CD
cd-name_1:
  type: mp3
  bitrate: 128  # optional, defaults to user config
  folders:
    __root__:
      - query: "'artist:Daft Punk'"
    folder_1:
      name: "Folder 1"  # optional, defaults to property key
      tracks:
        - query: "'Life in a Bubble I Blew'"
    folder_2:
      name: "Folder 2"
      tracks:
        - playlist: "/path/to/playlist.m3u"
    folder_3:
      name: "Folder 3"
      tracks:
        - playlist: "/path/to/playlist.m3u"
        - playlist: "relative/to/def_file/playlist.m3u"

# Audio CD
cd-name_2:
  type: audio
  populate_mode: soft_link  # optional, defaults to user config
  # populate_mode: hard_link
  # populate_mode: copy
  tracks:
    - query: "'artist:Foals' 'album:What Went Down'"
    - playlist: "/path/to/playlist.m3u"
    
```
12. User config must conform to the following syntax:
```yml
cdman:
  path: ~/Music/CDs
  threads: 8  # optional, defaults to hardware thread count
  mp3_bitrate: 128  # optional, defaults to 128
  audio_populate_mode: copy  # optional, defaults to copy
  cd_files:  # optional
    - ~/Music/CD Defs/cd1.yml
    - relative/to/home/cd2.yml
  cds:  # optional
    cd-name_1:
      # ... follows spec from CD definitions
```
12. There must be a CLI option for a dry run - where the system pretends to perform operations, but does not execute them.
13. The system must support listing tracks in their library that are not used in any of their defined CDs.
  - These CD definitions are defined by the path passed in and the user config
14. The system must report how many tracks successfully populated, moved, and failed.
15. The CLI must provide options to override user config
16. When populating tracks, the system must accurately determine if a folder is not present or has been moved or deleted.
17. When populating tracks, the system must accurately determine if a track was not fully converted
18. After populating tracks, the system will inform the user where to split their tracks to fit the files onto multiple CDs.
