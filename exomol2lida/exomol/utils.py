import warnings

import pandas as pd


class ExomolLineCommentError(Exception):
    pass


class ExomolLineValueError(Exception):
    pass


def parse_exomol_line(
        lines, n_orig, expected_comment=None, file_name=None, val_type=None,
        raise_warnings=False):
    """Line parser for the ExoMol files (.all and .def).

    List of the file lines is passed as well as the original length of the list.
    The top line of lines is popped (lines gets changed as an externality) and the
    line value is extracted and returned.
    If the expected_comment is passed, the comment in the top line (after # symbol)
    is asserted to equal the expected_comment.
    If the comment does not match (possible inconsistency), AssertionError is
    raised with the line number of the original file.

    Parameters
    ----------
    lines : list[str]
        List at first containing all the lines of the file which are then being
        popped one by one.
    n_orig : int
        The number of lines of the full file
    expected_comment : str
        The comment after the # symbol on each line is expected to match the
        passed expected comment.
    file_name : str
        The name of the file that lines belonged to (for error raising only).
    val_type : type
        The intended type of the parsed value, the value will be converted to.
    raise_warnings : bool
        If True, warning will be raised if the parsed comment does not match the
        expected comment.

    Returns
    -------
    str | int | float
        Value belonging to the top line in lines passed. Type is either str, or passed
        val_type.

    Raises
    ------
    ExomolLineCommentError
        If the top line does not have the required format of value # comment
    ExomolLineValueError
        If the value parsed from the top line cannot be converted to the val_type.

    Warnings
    --------
    UserWarning
        If the comment parsed from the top line does not match the expected_comment.
        Only if warn_on_comment is True.

    Examples
    --------
    >>> lns = ['1      # comment1',
    ...        'val2   # comment2',
    ...        'val3             ',
    ...        'val4   # comment4',]
    >>> n = len(lns)
    >>> parse_exomol_line(lns, n, expected_comment='comment1', val_type=int)
    1

    >>> lns
    ['val2   # comment2', 'val3             ', 'val4   # comment4']

    >>> parse_exomol_line(lns, n, expected_comment='comment2')
    'val2'

    >>> lns
    ['val3             ', 'val4   # comment4']

    >>> parse_exomol_line(lns, n, file_name='C60.def')
    Traceback (most recent call last):
      ...
    utils.ExomolLineCommentError: Unexpected line format detected on line 3 in C60.def

    >>> parse_exomol_line(
    ...     lns, n, expected_comment='comment4', file_name='foo', val_type=int)
    Traceback (most recent call last):
      ...
    utils.ExomolLineValueError: Unexpected value type detected on line 4 in foo

    >>> lns
    []
    """

    while True:
        try:
            line = lines.pop(0).strip()
        except IndexError:
            msg = f'Run out of lines'
            if file_name:
                msg += f' in {file_name}'
            raise ExomolLineValueError(msg)
        line_num = n_orig - len(lines)
        if line:
            break
        elif raise_warnings:
            msg = f'Empty line detected on line {line_num}'
            if file_name:
                msg += f' in {file_name}'
            warnings.warn(msg)
    try:
        val, comment = line.split('# ')
        val = val.strip()
    except ValueError:
        msg = f'Unexpected line format detected on line {line_num}'
        if file_name:
            msg += f' in {file_name}'
        raise ExomolLineCommentError(msg)
    if val_type:
        try:
            val = val_type(val)
        except ValueError:
            msg = f'Unexpected value type detected on line {line_num}'
            if file_name:
                msg += f' in {file_name}'
            raise ExomolLineValueError(msg)
    if comment != expected_comment and raise_warnings:
        msg = f'Unexpected comment detected on line {line_num}!'
        if file_name:
            msg += f' in {file_name}'
        warnings.warn(msg)
    return val


def load_dataframe_chunks(file_path, chunk_size, column_names=None, index_col=None):
    df_chunks = pd.read_csv(
        file_path, compression='bz2', sep=r'\s+', header=None, index_col=index_col,
        names=column_names, chunksize=chunk_size, iterator=True, low_memory=False
    )
    return df_chunks


def get_num_columns(file_path):
    for chunk in load_dataframe_chunks(file_path, chunk_size=1):
        num_cols = chunk.shape[1]
        return num_cols
