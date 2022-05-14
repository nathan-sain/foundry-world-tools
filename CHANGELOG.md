# Feb 22, 2021 - Initial release

FoundryWorldTools first release. Only works on Unix

# Mar 13, 2021

* Refactored to work on Windows computers
  * Updated complete example to include separate commands for Windows
* Added ability to rename / copy world directories

# April 26, 2021

This release is a complete rewrite of the utility with more robust path
support. Better config management, logging, and new commands and options have 
been added.

* Support for relative paths
* Support for logging to a file
* Better trash directory management
* Add default presets to new config files
* Added the download command
* Added the pull command
* Added --replace option to rewriteall
* Added --lower option to rewriteall

# May 26, 2021

* BUG FIX: Also update paths in the project's manifest JSON file
* BUG FIX: Properly handle --dataDir option
* FEATURE: Added --exclude-dir option on dedup command

# May 31, 2021

* BUG FIX: added routines to process dedup by file name. They were left out of the April rewrite
* BUG FIX: moved --edit option processing earlier in the cli processor to allow editing the config
  file before attempting to determine the location of the Foundry User Data Directory.
* Added additional debug statements
* Increase the version number to 0.3
* BUG FIX unable to use dedup --bycontent
* Increase the version number to 0.3.1

# June 18, 2021

* Added two nedb utilities: nedb2yaml and yaml2nedb
* Increase the version number to 0.4.0

# July 5, 2021

* Changed download command. Actor's images are called avatar and token now. Added an option to specify the base asset directory for downloaded images. Images will be stored in <world-dir>/<asset-dir>/<actor-name>/{avatar,token} now.

# July 11, 2021

* fixed a bug in rename function. On Windows the Python pathlib rename method refuses to overwrite files. Updated rename function to use the pathlib replace when overwrite of files is requested.

# Sept. 7, 2021

* Fixed a bug affecting the download command. If an actor object img or token.img property was null the download job failed. An error is now logged and the job will complete.
* Added new download type items

# Oct. 9, 2021

* Modified rewrite commands defaults to not search for quote marks around paths.

# May 16, 2022

* Modified the regular expression used to find remote assets for the pull command. Now the entire database is searched for remote paths. Previously only the value of img json keys were considered.
