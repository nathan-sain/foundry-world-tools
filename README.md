# Foundry World Tools (FWT)

A Python CLI for working with Foundry VTT world assets on the file system. FWT generally does two things when run; 1st it moves files and 2nd it updates the foundry databases with the new location of the file using a search and replace. In the case of duplicate files FWT does not delete files, only move them to a trash directory at the root of the world directory, if files are to be deleted that must be done manually. FWT makes a backup copy of any database files it rewrites using the original name with a .bak at the end. Regular expressions are used as patterns file renaming. FWT was created to help me clean up adventure modules exported from other VTTs, and I hope it can help you.

To make it easier to do repetitive tasks using the dedup and renameall commands it is possible to store presets in a config file.

fwt --help and fwt CMD --help will give brief usage information for the CLI and supported commands.

Install using pip `python3 -m pip install git+https://github.com/nathan-sain/foundry-world-tools.git`

## Currently the CLI supports the following commands

* **dedup:** scan the files in the world directory to detect duplicate files and move all but one of the duplicates into a Trash directory. Files can be filter by extension. Duplicates can be detected by files with the same base name in the same directory or by comparing the contents of all of the files in the world directory. The preferred duplicate can be determined using a pattern. 
    * Example 1: Using filename duplicate detection with the option --byname the files "big_map.png" and "big_map.webp" in the same directory are duplicate assets. Without the --preferred option the first in the order of detection will considered the preferred asset and all of the other duplicates will be moved to a trash directory. If webp files are preferred the option --preferred=".*webp" can be used in which case "big_map.png" will be moved the the Trash folder. `python3 -m foundryWorldTools dedup --byname --ext=".png" --ext=".webp" --preferred=".*webp" /fvtt/Data/worlds/myadventure` 
    * Example 2: Use content duplicate detection with the option --bycontent "scenes/token1.png" "characters/goblin_token.png" "journal/token5.png" are determined to be duplicates. Without the --preferred option the first in the order of detection is considered the preferred asset and all others will be moved to a trash directory. If the duplicate in the characters directory is preferred then the option --preferred="characters/.*" will cause the "characters/goblin_token.png" file to kept and "scenes/token1.png" and "journal/token5.png" to be moved to the trash directory. `python3 -m foundryWorldTools dedup --bycontent --prefered="characters/.*" /fvtt/Data/worlds/myadventure`

* **rename:** rename a asset in the database and move / copy the asset. This works on file assets and world directories.
    * Example: You accidentally uploaded a tile to the root of your FVTT data directory /fvtt/Data and you wanted it to be in /fvtt/Data/worlds/adventure1/tiles. `python3 -m foundryWorldTools rename /fvtt/Data/cart.png /fvtt/Data/worlds/adventure1/tiles/cart.png`
    * Example: You uploaded a asset into the shared Foundry Data directory and used it in all of your worlds, but you wish to have a separate copy in a world directory so you can copy the world to another server. In this case you can use the --keep-src option to leave the original asset in place for the other worlds. `python3 -m foundryWorldTools rename --keep-src /fvtt/Data/shared/token1.png /fvtt/Data/worlds/adventure/characters/elfman/token1.png`
    * Example: You want to copy a wold to a new version: `python3 -m foundryWorldTools rename --keep-src /fvtt/Data/worlds/firstworld /fvtt/Data/worlds/firstworldPart2`

* **renameall:** scan the world directory and rename files based on a pattern. Currently this only has one option --remove, which specifies a pattern for removing characters from file names.

* **replace:** replace one file with another. The file to be replaced, the target, is moved to a trash directory and the source file is moved to the path of the target.

# Complete Example
This example shows how to remove duplicate PNG files, replace all PNG images with WEBP images using the cwebp command, and then remove undesirable characters from the remaining files. The adventure1 world has many duplicate images. Some of the duplicates are stored in a folder called images/misc and it is preferred for images to be stored in the characters, journal, and scenes directories. **On windows don't use -rf with the rm command**

```
# python3 -m foundryWorldTools dedup --bycontent --ext ".png" --ext ".PNG" --preferred="<world_dir>/characters.*token.*" --preferred="<world_dir>/characters" --preferred="<world_dir>/journal" --preferred="<world_dir>/scenes" /fvtt/Data/worlds/adventure1 
# echo "Load the adventure in Foundry and check to make sure everything loads properly then delete Trash and backups"
# rm -rf /fvtt/Data/worlds/adventure1/Trash
# rm /fvtt/Data/worlds/adventure1/data/*bak
# rm /fvtt/Data/worlds/adventure1/packs/*bak
# echo "if files remain in the images/misc directory copy the individual files from images/misc to other preferred directories and rerun dedup"
# python3 -m foundryWorldTools dedup --bycontent --ext ".png" --ext ".PNG" --preferred="<world_dir>/characters.*token.*" --preferred="<world_dir>/characters" --preferred="<world_dir>/journal" --preferred="<world_dir>/scenes" /fvtt/Data/worlds/adventure1
# echo "Replace all png files with webp files"
# On Unix
# for file in $(find /fvtt/Data/worlds/adventure1 -iname '*png'); do cwebp -preset drawing -sharp_yuv -mt -psnr 45 "$file" -o "${file%*png}webp";done
# On Windows
# gci \fvtt\Data\worlds\adventure1 -R -include *.png | Foreach-Object { c:\bin\cwebp -preset drawing -sharp_yuv -mt -psnr 45 -o "$($_.FullName.split('.')[0]).webp" $_.FullName }
# python3 -m foundryWorldTools dedup --ext=".png" --ext=".PNG" --ext=".webp" --byname --preferred=".*webp" /fvtt/Data/worlds/adventure1
# echo "Load the adventure in Foundry and check to make sure everything loads properly then delete Trash and backups"
# rm -rf /fvtt/Data/worlds/adventure1/Trash
# rm /fvtt/Data/worlds/adventure1/data/*bak
# rm /fvtt/Data/worlds/adventure1/packs/*bak
# echo "Remove undesirable characters from files"
# python3 -m foundryWorldTools renameall --remove="([\[\] '])|(__)|[0-9]{3}_-_" /fvtt/Data/worlds/adventure
echo "Load the adventure in Foundry and check to make sure everything loads properly then delete Trash and backups"
# rm /fvtt/Data/worlds/adventure1/data/*bak
# rm /fvtt/Data/worlds/adventure1/packs/*bak
```

# Contribution

If you notice a bug or would like to request a feature please the open an issue. Better yet fork the repository and make a pull request!