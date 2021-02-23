import click
from foundryWorldTools import lib
logging = lib.logging


@click.group(invoke_without_command=True)
@click.option('--debug/--no-debug',default=False)
@click.option('--config',help="specify a config file to load",type=click.Path(exists=True,file_okay=True,resolve_path=True))
@click.option('--edit',is_flag=True,help='edit the presets file',default=False)
@click.option('--showpresets',is_flag=True,help='show presets avaliable',default=False)
@click.option('--preset',help='load a given preset. Where possible presets are merged with options otherwise options override presets')
@click.pass_context
def cli(ctx,debug,showpresets,preset,config,edit):
    """Commands for managing asset files in foundry worlds"""
    ctx.ensure_object(dict)
    if debug:
        logging.basicConfig(level = logging.DEBUG)
        ctx.obj['DEBUG'] = debug
        click.echo('Debug mode is on')
    config_data = lib.FWT_Config()
    if not config:
        config = lib.path.join(click.get_app_dir('foundryWorldTools'),"config.json")
        lib.logging.debug(f"No config file provided. Attempting to load config from {config}")
        if not lib.path.exists(config): config_data.create_config(config)
    if config:
        config_data.load(config)
    ctx.obj['CONFIG'] = config_data
    ctx.obj['CONFIG_LOADED'] = True
    ctx.obj['CONFIG_PATH'] = config
    if edit:
        click.edit(filename=config)

    if preset:
        if ctx.obj['CONFIG_LOADED']:
            presets = ctx.obj['CONFIG'].get("presets",{})
        try: 
            preset_obj = presets[preset]
        except NameError:
            ctx.fail("Preset not found: There are no presets defined")
        except KeyError:
            ctx.fail(f"Preset not found. Presets avaliable are: {', '.join(presets.keys())}")
        if not ctx.invoked_subcommand in preset_obj['command']:
            ctx.fail(f"Preset {preset} is not a valid preset for the {ctx.invoked_subcommand} command")
        ctx.obj['PRESET'] = preset_obj
    elif showpresets:
        if ctx.obj['CONFIG_LOADED']:
            presets = ctx.obj['CONFIG'].get("presets",{})
        try:
            click.echo(
                "\nPresets:\n"+"\n".join([
                    f"\t{k}: {v['command']} command, {v['description']}" for (k,v) in presets.items()
                ])
            )
        except NameError:
            ctx.fail("There are no presets defined")
    elif not ctx.invoked_subcommand:
        click.echo(ctx.get_help())

@cli.command()
@click.option('--ext',help='files with this extension will be checked. May be used multiple times.',multiple=True)
@click.option('--preferred',help='a pattern used to select a preferred file name from a list of duplicates. The string <world_dir> will be replaced with the full path to the world directory. May be used multiple times.',multiple=True)
@click.option('--byname',is_flag=True,help='method for finding duplicates',default=False)
@click.option('--bycontent',is_flag=True,help='method for finding duplicates',default=False)
@click.argument('world_dir',type=click.Path(exists=True,file_okay=False,resolve_path=True))
@click.pass_context
def dedup(ctx,world_dir,ext,preferred,byname,bycontent):
    """Scans for duplicate files and then removes duplicates and updates fvtt's databases.
    
    DIR should be a directory containing a world.json file"""
    dup_manager = lib.FWT_SetManager(world_dir)
    preset = ctx.obj.get('PRESET',None)
    if preset:
        preferred += tuple(preset.get('preferred',[]))
        byname = preset.get('byname',byname)
        bycontent = preset.get('bycontent',bycontent)
        ext += tuple(preset.get('ext',[]))
        click.echo(preferred)
    for pp in preferred: dup_manager.add_preferred_pattern(pp)
    for e in ext: dup_manager.add_file_extension(e)
    dup_manager.set_detect_method(byname=byname,bycontent=bycontent)
    dup_manager.scan()
    dup_manager.set_preferred_on_all()
    dup_manager.generate_rewrite_queue()
    dup_manager.process_rewrite_queue()
    dup_manager.process_file_queue()

@cli.command()
@click.option('--ext',help='files with this extension will be checked.May be used multiple times.',multiple=True)
@click.option('--remove',help='pattern for rewriting file names')
@click.argument('dir',type=click.Path(exists=True,file_okay=False,resolve_path=True))
@click.pass_context
def renameall(ctx,dir,ext,remove):
    """Scans files, renames based on a pattern and updates the world databases.
    
    DIR should be a directory containing a world.json file"""
    file_manager = lib.FWT_FileManager(dir)
    preset = ctx.obj.get('PRESET',None)
    if preset:
        ext += preset.get('ext',[])
        remove += remove or preset.get('remove',None)

    if not remove:
        click.fail("--remove is a required option")
    for e in ext: file_manager.add_file_extension(e)
    file_manager.add_rewrite_names_pattern(remove)
    file_manager.scan()
    file_manager.renameall()
    file_manager.generate_rewrite_queue()
    file_manager.process_rewrite_queue()
    try:
        file_manager.process_file_queue()
    except ValueError as e:
        click.echo(f"Unable to rename file:\n{e}")


@cli.command()
@click.argument('targets',type=click.Path(exists=True,file_okay=True,resolve_path=True))
@click.argument('src',type=click.Path(exists=True,file_okay=True,resolve_path=True))
@click.pass_context
def replace(ctx,src,targets):
    """Replace one file with another and update the world databases"""
    world_dir = lib.findWorldRoot(src)
    sm = lib.FWT_SetManager(world_dir)
    sm.add_set([src,targets])
    sm.add_preferred_pattern(src)
    sm.set_preferred_on_all()
    sm.generate_rewrite_queue()
    sm.process_rewrite_queue()
    sm.process_file_queue()


@cli.command()
@click.argument('src',type=click.Path(exists=True,file_okay=True,resolve_path=True))
@click.argument('target',type=click.Path(exists=False,resolve_path=True))
@click.option('--keep-src',is_flag=True,help='keep source file',default=False)
@click.pass_context
def rename(ctx,src,target,keep_src):
    """Rename a file and update the world databases"""
    world_dir = lib.findWorldRoot(src) or lib.findWorldRoot(target)
    if not world_dir:
        click.abort("Unable to determine the root directory of the fvtt world")
    fm = lib.FWT_FileManager(world_dir)
    file = fm.add_file(src)
    file.set_new_path(target)
    if keep_src:
        file.set_keep_src()
    fm.generate_rewrite_queue()
    fm.process_rewrite_queue()
    fm.process_file_queue()
