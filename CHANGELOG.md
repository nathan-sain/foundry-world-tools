# Feb 22, 2021 - Inital release

FoundryWorldTools first release. Only works on Unix

# Mar 13, 2021

* Refactored to work on Windows computers
  * Updated complete example to include seperate commands for Windows
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

* BUG FIX: Also update paths in the project's manafest JSON file
* BUG FIX: Properly handle --dataDir option
* FEATURE: Added --exclude-dir option on dedupe command