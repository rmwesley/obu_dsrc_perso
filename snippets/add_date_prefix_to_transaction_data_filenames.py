import pathlib
import datetime

local_transactions_storage_path_str = pathlib.Path('local_file_storage/transactions')

for file_path in local_transactions_storage_path_str.iterdir():
    # creation_time_float = file_path.stat().st_ctime
    modification_time_float = file_path.stat().st_mtime
    creation_date = datetime.datetime.fromtimestamp(modification_time_float)
    date_prefix = creation_date.strftime('%Y%m%dT%H%M%S')

    current_filename = file_path.name
    unprefixed_filename = file_path.name.split('_')[1]
    prefixed_filename = f'{date_prefix}_{unprefixed_filename}'
    # prefixed_filename = f'{date_prefix}_{current_filestem}.json'
    print(prefixed_filename)

    new_path = file_path.with_name(prefixed_filename)
    # file_path.with_stem(current_filestem)
    # file_path.with_suffix('.json')
    file_path.rename(new_path)
