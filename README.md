# Foundry World Tools (FWT)

A Python CLI for working with Foundry VTT project assets on the file system. FWT generally does two things when run; 1st it moves files and 2nd it updates the foundry databases with the new location of the file using a search and replace. In the case of duplicate files FWT does not delete files, only move them to a trash directory at the root of the world directory, if files are to be deleted that must be done manually. FWT makes a backup copy of any database files it rewrites using the original name with a .bak.X at the end. Regular expressions are used as patterns when preforming file renaming and preferred file matching. FWT was created to help me clean up adventure modules exported from other VTTs, and I hope it can help you.

`fwt --help` and `fwt CMD --help` will give brief usage information for the CLI and supported commands.

# Installation

Install using pip `python3 -m pip install git+https://github.com/nathan-sain/foundry-world-tools.git`

On windows the cli command isn't installed in a directory that is in the binary path. In this case you have three options:

1. use `python3 -m foundryWorldTools` instead of `fwt` to execute the cli
2. find the fwt cli command and put it in your path. It's usually in an AppData/Local/Packages/Python3X/Scripts
3. create a PowerShell function to run the python module with the fwt command `Function fwt {python3 -m foundryWorldTools @Args}`


# Notes

## Foundry User Data Directory

When fwt changes the name or location of files it must update the database files of a Foundry project. Foundry databases store file paths relative to the Foundry user data directory (fudd). Therefore in order for fwt to correctly update file paths in the database it must know the location of the fudd. If the configuration file does not have the fudd set or the --dataDir option is not set fwt will attempt to auto detect the fudd path. This is usually pretty easy if fwt is used interactively in a project directory. But if fwt run from outside of the fudd it will be necessary to set the dataDir in the config file or by using the --dataDir option. `fwt --dataDir=e:\Data renameall --replace=/_/-/ e:\Data\worlds\lmop`

## File paths

fwt is intended to be use interactively on the command line. Where files and directories are required as arguments you can specify them as you would with any command-line to work with files, e.g. `fwt rename token.png ../../characters/wizard/`

## Config file and presets

A JSON formatted config file can be used to store the location of the Foundry user data directory, dataDir, as well as presets. It is possible to see the config file default location and to open the config file in the default editor using `fwt --edit`. It is also possible to manually set the config file path using `fwt --config=` option. A config file must exist in order to be loaded. If an empty config file is detected it will be populated with the default configuration. To create a new file with the default configuration use the `--mkconfig` flag. When the --mkconfig flag is present, file exists, and isn't empty it will be left as is and a warning will be logged. 

* create a default config file in the default path
    `fwt --mkconfig`
* create a default config file in a specific path
    `fwt --mkconfig --config=~/fwt.json`

fwt supports storing presets for commands which allow consistent application of options across multiple uses and prevent the need to type long commands repeatedly. fwt ships with some default presets setup in the config file.


* `fwt --preset=imgDedup dedup "myadventure"`
* `fwt --config=~/fwt.json --preset=fixr20 renameall "worlds/myadventure"`

## Logging

fwt can be configured to log messages to the console or to a file. To specify a file for logging use the `--logfile` option with a path for the log file. File logging is always at the debug level. To change the console logging level use the `--loglevel` option with any of INFO,WARNING,ERROR,DEBUG,QUIET.

* `fwt --logfile=/tmp/lmop_dedup.log --preset=imgDedup dedup /Data/worlds/lmop`

## Deleting files

fwt doesn't delete any files. When file paths are removed from the the database the corresponding files are moved to a trash directory located in the root of the project directory. Additionally when databases are to be modified, before changes are made, a unmodified version of the database file is stored in the trash directory. fwt uses a incrementing trash directory scheme. The first trash directory is trash/session.0 and on consecutive runs new trash directories will be created: trash/session.1, trash/session.2 etc. This makes it possible to preserve files and databases across multiple runs as well as easily removing all of the trash files by deleting the trash folder.

# Usage

## Commands

* **dedup:** scan the files in the world directory to detect duplicate files and move all but one of the duplicates into a Trash directory. Files can be filtered by extension. Duplicates can be detected by files with the same base name in the same directory or by comparing the contents of all of the files in the world directory. The preferred duplicate can be determined using a regular expression pattern. Patterns can be prefixed with the string `<project_dir>` which will be substituted for the absolute path of the project director for more precise matching.
    * Example 1: Using filename duplicate detection with the option `--byname` the files "big_map.png" and "big_map.webp" in the same directory are duplicate assets. Without the --preferred option the first in the order of detection will be considered the preferred asset and all of the other duplicates will be moved to a trash directory. If webp files are preferred the option `--preferred=".*webp"` can be used in which case "big_map.png" will be moved the the Trash folder.
    
        `fwt dedup --byname --ext=".png" --ext=".webp" --preferred=".*webp" /fvtt/Data/worlds/myadventure` 
        
    * Example 2: Using content duplicate detection with the option `--bycontent` files "scenes/token1.png" "characters/goblin_token.png" "journal/token5.png" are determined to be duplicates. Without the --preferred option the first in the order of detection is considered the preferred asset and all others will be moved to a trash directory. If duplicates in the characters directory are preferred then the option --preferred="characters/.*" will cause the "characters/goblin_token.png" file to kept and "scenes/token1.png" and "journal/token5.png" to be moved to the trash directory.
    
         `fwt --bycontent --prefered="characters/.*" /fvtt/Data/worlds/myadventure`
    
    * Example 3: Using a preset called imgDedup and excluding all directories named sides from being scanned

         `fwt --preset=imgDedup dedup --exclude-dir=sides myadventure`

* **rename:** rename a asset in the database and move / copy the asset. This works on file assets and world directories.
    * Example: You accidentally uploaded a tile to the root of your FVTT user data directory  and you want it to be in tiles directory of the world of your current working directory. 

        `fwt rename ../../cart.png tiles/`
    * Example: You uploaded a asset into the shared Foundry Data directory and used it in all of your worlds, but you wish to have a separate copy in a world directory so you can copy the world to another server. In this case you can use the --keep-src option to leave the original asset in place for the other worlds. When moving files outside of the project directory tt is best use --dir=/fvtt/Data/worlds/adventure to specify which project database files should be updated. 

        `fwt rename --keep-src /fvtt/Data/shared/token1.png /fvtt/Data/worlds/adventure/characters/elfman/token1.png`
    * Example: You want to create a new world based on an exiting world: 

        `fwt rename --keep-src firstworld firstworldPart2`

* **renameall:** scan the world directory and rename files based on a pattern. Currently this only has one option --remove, which specifies a pattern for removing characters from file names.
    * Example: Replace all of the underscores with dashes in the file names 

        `fwt renameall --replace '/_/-/' /fvtt/Data/worlds/adventure`
    * Example: Convert all of the file names to lower case

        `fwt renameall --lower adventure`

* **download:** A command to gather image locations and determine if the images are hosted remotely. In the case that images are remotely hosted they are downloaded to the local project directory. The download location is determined by inspecting the other image locations of the object. If any of them are local then the remote file is downloaded to the same directory as existing images. If all images are remote then a default directory is choose by object type. **currently only actors are checked for remote assets**
    * Example: You have actors which contain links to remote assets in their biography HTML.

        `fwt download worlds/lmop`

* **pull:** A command to copy all assets stored in directories outside of the project directory. If a project has file paths to a shared asset directory or a project has file paths to a module this command can be used to copy all of the files into the project directory. Allow the project to be copied to another server without depending on existence of the external assets. 
    * Example: You have scene backgrounds stored in a content module and you want to copy them into your project directory

        `fwt pull --from=/Data/modules/madmaps --to=/Data/worlds/darkest-hour`

# Complete Example
This example shows how to remove duplicate PNG files, replace all PNG images with WEBP images using the cwebp command, and then remove undesirable characters from the remaining files. The adventure1 world has many duplicate images. Some of the duplicates are stored in a folder called images/misc and it is preferred for images to be stored in the characters, journal, and scenes directories. **On windows don't use -rf with the rm command**

```sh
### Dedup by content to find extra files
fwt dedup --bycontent --ext ".png" --preferred="<world_dir>/characters.*token.*" --preferred="<world_dir>/characters" --preferred="<world_dir>/journal" --preferred="<world_dir>/scenes" /fvtt/Data/worlds/adventure1 

# Load the adventure in Foundry and check to make sure everything loads properly then delete Trash and backups
rm -rf /fvtt/Data/worlds/adventure1/trash

# if files remain in the images/misc directory copy the individual files from images/misc to other preferred directories and rerun dedup
fwt dedup --bycontent --ext ".png" --preferred="<world_dir>/characters.*token.*" --preferred="<project_dir>/characters" --preferred="<project_dir>/journal" --preferred="<project_dir>/scenes" /fvtt/Data/worlds/adventure1
# repeat testing and detete Trash and backups...
```

```sh
### shell script to preform webp image conversion and then remove extra files with FWT
###### On Unix
for file in $(find /fvtt/Data/worlds/adventure1 -iname '*png'); do cwebp -preset drawing -sharp_yuv -mt -psnr 45 "$file" -o "${file%*png}webp";done
###### On Windows
gci \fvtt\Data\worlds\adventure1 -R -include *.png | Foreach-Object { c:\bin\cwebp -preset drawing -sharp_yuv -mt -psnr 45 -o "$($_.FullName.split('.')[0]).webp" $_.FullName }
# Dedup by name to remove the PNG files
fwt dedup --ext=".png" --ext=".webp" --byname --preferred=".*webp" /fvtt/Data/worlds/adventure1
# Load the adventure in Foundry and check to make sure everything loads properly then delete Trash and backups
```

```sh
### Use replaceall to remove or replace undesirable characters from files and convert path to lower case
fwt renameall --remove="[0-9]{3}_-_" --replace="/_+/-/" --lower worlds/adventure
# Load the adventure in Foundry and check to make sure everything loads properly then delete Trash and backups"
```

# Config file example

```json
{   
    "dataDir":"/fvtt/Data",
    "presets":{
        "imgDedup":{
            "description":"Find duplicate image files and chooses files from the characters,journal,scenes directories to keep",
            "command":"dedup",
            "bycontent":true,
            "ext": [".png",".jpg",".jpeg",".gif",".webp"],
            "preferred":["<project_dir>/characters.*token.*","<project_dir>/characters","<project_dir>/journal.*token.*","<project_dir>/journal","<project_dir>/scenes"]
        }
    }
}

```

# Contribution

If you notice a bug or would like to request a feature please the open an issue. Better yet fork the repository and make a pull request!