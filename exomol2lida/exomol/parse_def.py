from collections import namedtuple
from pathlib import Path

import requests
from pyvalem.formula import Formula, FormulaParseError

from exomol2lida.exomol.utils import (
    parse_exomol_line, ExomolLineValueError, ExomolLineCommentError)

file_dir = Path(__file__).parent.resolve()
project_dir = file_dir.parent.parent
test_resources = project_dir.joinpath('test', 'resources')


class ExomolDefParseError(Exception):
    pass


ExomolDefBase = namedtuple(
    'ExomolDefBase',
    ['raw_text', 'id', 'iso_formula', 'iso_slug', 'dataset_name', 'version',
     'inchi_key', 'isotopes', 'mass', 'symmetry_group', 'irreducible_representations',
     'max_temp', 'num_pressure_broadeners', 'dipole_availability', 'num_cross_sections',
     'num_k_coefficients', 'lifetime_availability', 'lande_factor_availability',
     'num_states', 'quanta_cases', 'quanta', 'num_transitions', 'num_trans_files',
     'max_wavenumber', 'high_energy_complete']
)

Isotope = namedtuple(
    'Isotope', 'number element_symbol'
)

IrreducibleRepresentation = namedtuple(
    'IrreducibleRepresentation', 'id label nuclear_spin_degeneracy'
)

QuantumCase = namedtuple(
    'QuantumCase', 'label'
)

Quantum = namedtuple(
    'Quantum', 'label format description'
)


class ExomolDef(ExomolDefBase):
    """
    A structured named tuple containing all the data from a parsed .def file.

    Also contains couple of additional methods on the data, such as the quanta_labels
    property.

    Attributes
    ----------
    all the attributes defined in ExomolDefBase (see the namedtuple call)
    """

    def get_quanta_labels(self):
        """
        List of quanta specified by the .def file.

        Returns
        -------
        list[str]
            List of quanta specified by the .def file
        """
        return [q.label for q in self.quanta]

    def get_states_header_mandatory(self):
        """
        List of the mandatory columns expected in the .states file belonging to this
        .def file.

        Returns
        -------
        list[str]
            First 4 - 6 columns in the .states file as expected, including the
            state index.
        """
        header = ['i', 'E', 'g_tot', 'J']
        if self.lifetime_availability:
            header.append('tau')
        if self.lande_factor_availability:
            header.append('g_J')
        return header

    def get_states_header(self):
        """
        List of all the columns expected in the .states file belonging to this
        .def file

        Returns
        -------
        list[str]
            List of column names expected in the relevant .states file
        """
        return self.get_states_header_mandatory() + self.get_quanta_labels()


def _get_exomol_def_raw(
        path=None, molecule_slug=None, isotopologue_slug=None, dataset_name=None
):
    """Get the raw text of a .def file.

    If called with a valid path (e.g. on the ExoWeb server or on a local test repo),
    the file under the path is read and returned, if called with None (default),
    the file is requested over https under the relevant URL via the ExoMol public
    API. In this case, molecule_slug, isotopologue_slug, and dataset_name must be
    supplied.

    Parameters
    ----------
    path : str | Path | None
        Path leading to the exomol.all file. If None is passed, the function requests
        the file from the url
        'https://www.exomol.com/db/<mol>/<iso>/<ds>/<iso>__<ds>.def'.
        In those cases, all the mol, iso and ds must be passed!
    molecule_slug : str
    isotopologue_slug : str
    dataset_name : str

    Returns
    -------
    str
        Raw text of the relevant .def file.
    """
    if path is None:
        if not all([molecule_slug, isotopologue_slug, dataset_name]):
            raise ValueError('If path not specified, you must pass all the other '
                             'parameters!')
        url = f'https://www.exomol.com/db/{molecule_slug}/{isotopologue_slug}/' \
              f'{dataset_name}/{isotopologue_slug}__{dataset_name}.def'
        return requests.get(url).text
    else:
        with open(path, 'r') as fp:
            return fp.read()


def _parse_exomol_def_raw(exomol_def_raw, file_name, raise_warnings=True):
    """Parse the raw text of the .def file.

    Parse the text and construct the ExomolDef object instance holding all
    the data from the .def file in a nice nested data structure of named tuples.

    Parameters
    ----------
    exomol_def_raw : str
        Raw text of the .def file. Can be obtained by calling
        _get_exomol_def_raw function.
    file_name : str
        Name of the .def file (for error logging purposes only)
    raise_warnings : bool
        If to raise warnings. Warning will be raised if an inconsistent def file is
        detected, but still can be parsed.

    Returns
    -------
    ExomolDef
        Custom named tuple holding all the (now structured) data. See the
        ExomolDefBase namedtuple instance. This class also defines additional
        functionality on top of the ExomolDefBase, such as quanta_labels attribute.
    """
    lines = exomol_def_raw.split('\n')
    n_orig = len(lines)

    def parse_line(expected_comment, val_type=None):
        return parse_exomol_line(
            lines, n_orig, expected_comment=expected_comment, file_name=file_name,
            val_type=val_type, raise_warnings=raise_warnings)

    # catch all the parse_line-originated errors and wrap them in a higher-level
    # error:
    try:
        kwargs = {
            'raw_text': exomol_def_raw,
            'id': parse_line('ID'),
            'iso_formula': parse_line('IsoFormula'),
            'iso_slug': parse_line('Iso-slug'),
            'dataset_name': parse_line('Isotopologue dataset name'),
            'version': parse_line('Version number with format YYYYMMDD', int),
            'inchi_key': parse_line('Inchi key of molecule'),
            'isotopes': []
        }
        num_atoms = parse_line('Number of atoms', int)
        try:
            formula = Formula(kwargs['iso_formula'])
        except FormulaParseError as e:
            raise ExomolDefParseError(f'{str(e)} (raised in {file_name})')
        if formula.natoms != num_atoms:
            ds_name = f'{kwargs["iso_slug"]}__{kwargs["dataset_name"]}.def'
            raise ExomolDefParseError(
                f'Incorrect number of atoms in {ds_name}'
            )
        for i in range(num_atoms):
            isotope_kwargs = {
                'number': parse_line(f'Isotope number {i + 1}', int),
                'element_symbol': parse_line(f'Element symbol {i + 1}')
            }
            isotope = Isotope(**isotope_kwargs)
            kwargs['isotopes'].append(isotope)
        iso_mass_amu = float(parse_line('Isotopologue mass (Da) and (kg)').split()[0])
        kwargs.update({
            'mass': iso_mass_amu,
            'symmetry_group': parse_line('Symmetry group'),
            'irreducible_representations': []
        })
        num_irreducible_representations = int(
            parse_line('Number of irreducible representations'))
        for _ in range(num_irreducible_representations):
            ir_kwargs = {
                'id': parse_line('Irreducible representation ID', int),
                'label': parse_line('Irreducible representation label'),
                'nuclear_spin_degeneracy': parse_line(
                    'Nuclear spin degeneracy', int)
            }
            ir = IrreducibleRepresentation(**ir_kwargs)
            kwargs['irreducible_representations'].append(ir)
        kwargs.update({
            'max_temp': parse_line('Maximum temperature of linelist', float),
            'num_pressure_broadeners': parse_line(
                'No. of pressure broadeners available', int),
            'dipole_availability': bool(
                parse_line('Dipole availability (1=yes, 0=no)', int)),
            'num_cross_sections': parse_line(
                'No. of cross section files available', int),
            'num_k_coefficients': parse_line(
                'No. of k-coefficient files available', int),
            'lifetime_availability': bool(
                parse_line('Lifetime availability (1=yes, 0=no)', int)),
            'lande_factor_availability': bool(
                parse_line('Lande g-factor availability (1=yes, 0=no)', int)),
            'num_states': parse_line('No. of states in .states file', int),
            'quanta_cases': [],
            'quanta': []
        })
        num_quanta_cases = parse_line('No. of quanta cases', int)
        # TODO: it is not entirely clear if num_quanta and related blocks are nested
        #       under a quanta case, or not. If they are, I need to change the data
        #       structures, and rewrite the parser a bit.
        for _ in range(num_quanta_cases):
            kwargs['quanta_cases'].append(
                QuantumCase(label=parse_line('Quantum case label')))
        num_quanta = parse_line('No. of quanta defined', int)
        for i in range(num_quanta):
            q_kwargs = {
                'label': parse_line(f'Quantum label {i + 1}'),
                'format': parse_line(f'Format quantum label {i + 1}'),
                'description': parse_line(f'Description quantum label {i + 1}')
            }
            quantum = Quantum(**q_kwargs)
            kwargs['quanta'].append(quantum)
        kwargs.update({
            'num_transitions': parse_line('Total number of transitions'),
            'num_trans_files': parse_line('No. of transition files'),
            'max_wavenumber': parse_line('Maximum wavenumber (in cm-1)'),
            'high_energy_complete': parse_line(
                'Higher energy with complete set of transitions (in cm-1)'),
        })

        return ExomolDef(**kwargs)
    except (ExomolLineValueError, ExomolLineCommentError) as e:
        raise ExomolDefParseError(str(e))


def parse_exomol_def(
        path=None, molecule_slug=None, isotopologue_slug=None, dataset_name=None,
        raise_warnings=False
):
    """Parse the .def file.

    Parse the text and construct the ExomolDef object instance holding all
    the data from the .def file in a nice nested data structure of named tuples.
    If called with a valid path (e.g. on the ExoWeb server or on a local test repo),
    the file under the path parsed, if called with None (default),
    the file is requested over https under the relevant URL via the ExoMol public
    API. In this case, molecule_slug, isotopologue_slug, and dataset_name must be
    all, supplied or a ValueError is raised.

    Parameters
    ----------
    path : str | Path | None
        Path leading to the exomol.all file. If None is passed, the function requests
        the file from the url
        'https://www.exomol.com/db/<mol>/<iso>/<ds>/<iso>__<ds>.def'.
        In those cases, all the mol, iso and ds must be passed!
    molecule_slug : str
    isotopologue_slug : str
    dataset_name : str
    raise_warnings : bool

    Returns
    -------
    ExomolDef
        Custom named tuple holding all the (now structured) data. See the
        ExomolDefBase namedtuple instance. This class also defines additional
        functionality on top of the ExomolDefBase, such as quanta_labels attribute.

    Examples
    --------
    >>> parse_exomol_def(path='foo.def')
    Traceback (most recent call last):
      ...
    FileNotFoundError: [Errno 2] No such file or directory: 'foo.def'

    >>> exomol_def = parse_exomol_def(path=test_resources / '40Ca-1H__Yadin.def')
    >>> type(exomol_def)
    <class 'exomol2lida.exomol.parse_def.ExomolDef'>

    >>> exomol_def.id
    'EXOMOL.def'

    >>> exomol_def.dataset_name
    'Yadin'

    >>> type(exomol_def.isotopes[0])
    <class 'exomol2lida.exomol.parse_def.Isotope'>

    >>> exomol_def.get_quanta_labels()
    ['par', 'v', 'N', 'e/f']

    >>> exomol_def.get_states_header()
    ['i', 'E', 'g_tot', 'J', 'tau', 'par', 'v', 'N', 'e/f']

    >>> parse_exomol_def(molecule_slug='foo')
    Traceback (most recent call last):
      ...
    ValueError: If path not specified, you must pass all the other parameters!
    """
    raw_text = _get_exomol_def_raw(
        path=path, molecule_slug=molecule_slug, isotopologue_slug=isotopologue_slug,
        dataset_name=dataset_name)
    if path is not None:
        file_name = Path(path).name
    else:
        file_name = f'{isotopologue_slug}__{dataset_name}.def'
    return _parse_exomol_def_raw(raw_text, file_name, raise_warnings=raise_warnings)
