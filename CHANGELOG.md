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

# May 26

* BUG FIX: Also update paths in the project's manifest JSON file
* BUG FIX: Properly handle --dataDir option
* FEATURE: Added --exclude-dir option on dedup command

# May 31

* BUG FIX: added routines to process dedup by file name. They were left out of the April rewrite
* BUG FIX: moved --edit option processing earlier in the cli processor to allow editing the config
  file before attempting to determine the location of the Foundry User Data Directory.
* Added additional debug statements
* Increase the version number to 0.3
* BUG FIX unable to use dedup --bycontent
* Increase the version number to 0.3.1

# June 18

* Added two nedb utilities: nedb2yaml and yaml2nedb
* Increase the version number to 0.4.0
