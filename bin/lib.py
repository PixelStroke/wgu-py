"""
coding=utf-8
"""
from pathlib import Path
import os
import logging
import re
import datetime
import pandas
import yaml
#import tempfile

# Global variables
CONFS = None
BATCH_NAME = None
BATCH_OUTPUT_FOLDER = None


def load_confs(confs_path='conf/conf.yaml'):
    """
    Load configurations from file.

     - If configuration file is available, load it
     - If configuraiton file is not available attempt to load configuration template

    Configurations are never explicitly validated.
    :param confs_path: Path to a configuration file, appropriately formatted for this application
    :type confs_path: str
    :return: Python native object, containing configuration names and values
    :rtype: dict
    """
    global CONFS

    if CONFS is None:

        template_path = confs_path + '.template'
        msg = F"Attempting to load conf from confs_path: {confs_path} or template_path: {template_path}"
        logging.info(msg)
        if Path(confs_path).exists():
            msg = F"confs_path: {confs_path} exists, attempting to load"
            logging.info(msg)
            with open(confs_path, encoding=str) as conf_file:
                CONFS = yaml.load(conf_file, Loader=yaml.FullLoader)
        elif Path(template_path).exists():
            msg = F"confs_path: {confs_path} does not exist, attempting to load template path: {template_path}"
            logging.warning(msg)
            with open(template_path, encoding=str) as template_file:
                CONFS = yaml.load(template_file, Loader=yaml.FullLoader)
        else:
            err = F"Neither confs_path: {confs_path} or template_path: {template_path} are available."
            logging.error(err)
            exc = "file not available at specified path"
            raise ValueError(F'Configuration: {exc}')

    return CONFS


def get_conf(conf_name):
    """
    Get a configuration parameter by its name
    :param conf_name: Name of a configuration parameter
    :type conf_name: str
    :return: Value for that conf (no specific type information available)
    """
    return load_confs()[conf_name]


def get_batch_name():
    """
    Get the name of the current run. This is a unique identifier for each run of this application
    :return: The name of the current run. This is a unique identifier for each run of this application
    :rtype: str
    """
    global BATCH_NAME

    if BATCH_NAME is None:
        logging.info('Batch name not yet set. Setting batch name.')
        batch_prefix = get_conf('batch_prefix')
        model_choice = get_conf('model_choice')
        datetime_str = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat())+'Z'
        BATCH_NAME = '_'.join([batch_prefix, model_choice, datetime_str])
        msg = F"Batch name set to: {BATCH_NAME}"
        logging.info(msg)
    return BATCH_NAME


def get_batch_output_folder():
    """Get the path to the output folder for the current batch."""
    global BATCH_OUTPUT_FOLDER
    if BATCH_OUTPUT_FOLDER is None:
        BATCH_OUTPUT_FOLDER = os.path.join(get_conf('output_path'), get_batch_name())
        os.mkdir(BATCH_OUTPUT_FOLDER)
        msg = F"Batch output folder set to: {BATCH_OUTPUT_FOLDER}"
        logging.info(msg)
    return BATCH_OUTPUT_FOLDER


def archive_dataset_schemas(step_name, local_dict, global_dict):
    """
    Archive the schema for all available Pandas DataFrames

     - Determine which objects in namespace are Pandas DataFrames
     - Pull schema for all available Pandas DataFrames
     - Write schemas to file

    :param step_name: The name of the current operation (e.g. `extract`, `transform`, `model` or `load`)
    :param local_dict: A dictionary containing mappings from variable name to objects.
        This is usually generated by calling `locals`
    :type local_dict: dict
    :param global_dict: A dictionary containing mappings from variable name to objects.
        This is usually generated by calling `globals`
    :type global_dict: dict
    :return: None
    :rtype: None
    """
    msg = F"Archiving schema for all available Pandas DataFrames for step: {step_name}"
    logging.info(msg)

    # Reference variables
    data_schema_dir = os.path.join(get_batch_output_folder(), 'schemas')
    if not os.path.exists(data_schema_dir):
        os.makedirs(data_schema_dir)
    schema_output_path = os.path.join(data_schema_dir, step_name + '.csv')
    schema_agg = list()

    env_variables = dict()
    env_variables.update(local_dict)
    env_variables.update(global_dict)

    # Filter down to Pandas DataFrames
    data_sets = filter(lambda x: type(x[1]) == pandas.DataFrame, env_variables.items())
    data_sets = dict(data_sets)

    header = pandas.DataFrame(columns=['variable', 'type', 'data_set'])
    schema_agg.append(header)

    for (data_set_name, data_set) in data_sets.items():
        # Extract variable names
        msg = F"Extracting variable names for data_set: {data_set_name}"
        logging.info(msg)

        local_schema_df = pandas.DataFrame(data_set.dtypes, columns=['type'])
        local_schema_df['data_set'] = data_set_name

        schema_agg.append(local_schema_df)

    # Aggregate schema list into one data frame
    agg_schema_df = pandas.concat(schema_agg)

    # Write to file
    agg_schema_df.to_csv(schema_output_path, index_label='variable')

def normalize_column_name(input_string):
    """Normalize column names to be compatible with the schema file format"""
    return_value = input_string.lower()
    return_value = re.sub(r'\s+', '_', return_value)
    return_value = re.sub(r'[^0-9a-zA-Z_]+', '', return_value)
    return_value = return_value.strip('_')
    return return_value