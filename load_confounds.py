"""
A function that is used to load confound parameters generated by FMRIPREP.

Authors: Dr. Pierre Bellec, Francois Paugam, Hanad Sharmarke
"""
import pandas as pd
from sklearn.decomposition import PCA

motion_6params = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]

motion_models = {
    "6params": "{}",
    "derivatives": "{}_derivative1",
    "square": "{}_power2",
    "full": "{}_derivative1_power2",
}

confound_dict = {
    "motion": ["trans", "rot"],
    "matter": ["csf", "white_matter"],
    "high_pass_filter": ["cosine"],
    "compcor": ["comp_cor"],
}


minimal = (
    confound_dict["motion"]
    + confound_dict["high_pass_filter"]
    + confound_dict["matter"]
)
confound_dict["minimal"] = minimal


def _confound_strat(strategy, confound_raw):
    """
    Retrieves the column names from raw confounds file

    Parameters
        strategy: string

                can be one of five keys found in confound_dict.

               -minimal: basic strategy that uses motion, high pass filter, csf and white matter parameters
               -motion: ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
               -high_pass_filter = ["cosine00", "cosine01", ..]
               -matter: ['csf', 'csf_derivative1_power2', 'csf_derivative1', 'white_matter','white_matter_derivative1_power2',
                'white_matter_derivative1','white_matter_power2', 'csf_power2']
               -compcor: ["t_comp_cor_00","t_comp_cor_01",..]
               

        confounds_raw: Pandas Dataframe

                the raw confounds from fmriprep

    Returns

        param: list

                a list of column names from confound_raw header
    """

    param = [
        col
        for col in confound_raw.columns
        for conf in confound_dict[strategy]
        if (conf in col)
    ]
    return param


def _add_motion_model(motion_model):
    """
    Add the motion model confounds to the list of motion confounds.

    Parameters

        motion_model: string

                Name of the motion model to use

    Returns

        motion_confounds: set

                motions confounds to use
    """
    if motion_model != "full":
        motion_confounds = set(
            motion_6params
            + [motion_models[motion_model].format(mot) for mot in set(motion_6params)]
        )
    else:
        motion_confounds = set(
            [
                motion_models[model].format(mot)
                for mot in set(motion_6params)
                for model in motion_models.keys()
            ]
        )

    return motion_confounds


def _pca_motion(
    confounds_out, confounds_raw, n_components=0.95, motion_model="6params",
):
    """
    Reduce the motion paramaters using PCA.

    Parameters
        confounds_out: Pandas Dataframe

                Confounds that will be loaded

        confounds_raw: Pandas Dataframe

                The raw confounds from fmriprep

        motion_confounds: List of strings

                Names of the motion confounds to do the PCA on

        n_compenents: int,float

                The number of compnents for PCA

                -if ``0 < n_components < 1``, n_components is percentage that represents the amount of variance that needs to be explained
                -if n_components == 0, the raw motion parameters are returned
                -if n_components >1, the number of components are returned

    Return
        confounds_out:  Pandas DataFrame

                A reduced version of FMRIPREP confounds based on strategy specified by user
        
        

    """

    # Run PCA to reduce parameters

    motion_confounds = _add_motion_model(motion_model)
    motion_parameters_raw = confounds_raw[list(motion_confounds)]

    if n_components == 0:
        confounds_pca = motion_parameters_raw

    else:
        motion_parameters_raw = motion_parameters_raw.dropna()
        pca = PCA(n_components=n_components)
        confounds_pca = pd.DataFrame(pca.fit_transform(motion_parameters_raw.values))
        confounds_pca.columns = [
            "motion_pca_" + str(col + 1) for col in confounds_pca.columns
        ]

    # Add motion parameters to confounds dataframe
    confounds_out = pd.concat((confounds_out, confounds_pca), axis=1)

    return confounds_out


def _load_confounds_main(
    confounds_raw, strategy=["minimal"], n_components=0.95, motion_model="6params"
):
    """
    Load confounds from fmriprep

    Parameters

        confounds_raw: Pandas Dataframe or path to tsv file

                       Raw confounds from fmriprep


        strategy: List of strings

                       The strategy used to select a subset of the confounds from fmriprep: each string can be
                       either the name of one of the following subset of confounds or the name of a confound to add.

                       -minimal: basic strategy that uses motion, high pass filter, csf and white matter parameters
                       -motion: ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
                       -high_pass_filter = ["cosine00", "cosine01", ..]
                       -matter: ['csf', 'csf_derivative1_power2', 'csf_derivative1', 'white_matter','white_matter_derivative1_power2', 'white_matter_derivative1',
                       'white_matter_power2', 'csf_power2']
                       -compcor: ["t_comp_cor_00","t_comp_cor_01",..]


        motion_model: String

                Temporal and quadratic terms for head motion estimates

                -6params: standard motion parameters (6)
                -square: standard motion paramters + quadratic terms (12)
                -derivatives: standard motion paramters + derivatives (12)
                -full: standard motion paramteres + derivatives + quadratic terms + squared derivatives (24)


    Returns

        confounds_out:  Pandas DataFrame

                A reduced version of FMRIPREP confounds based on strategy specified by user
    """

    # Convert tsv file to pandas dataframe
    if not isinstance(confounds_raw, pd.DataFrame):
        confounds_raw = pd.read_csv(confounds_raw, delimiter="\t", encoding="utf-8")

    # Add chosen confounds based on strategy to dataframe
    confounds_of_interest = set()
    confounds_out = pd.DataFrame()

    for strat in strategy:
        if strat in confound_dict.keys():

            confounds_of_interest |= set(_confound_strat(strat, confounds_raw))
        else:
            confounds_of_interest.add(strat)

    # Remove motion confounds and concatenate columns to confounds_out
    non_motion_confounds = [
        conf
        for conf in confounds_of_interest
        if (("rot" not in conf) and ("trans" not in conf))
    ]

    confounds_out = pd.concat(
        (confounds_out, confounds_raw[list(non_motion_confounds)]), axis=1
    )

    # Apply PCA on motion confounds
    motion_bool = set(motion_6params) & confounds_of_interest
    if motion_bool:
        confounds_out = _pca_motion(
            confounds_out, confounds_raw, n_components, motion_model,
        )

    return confounds_out


def _load_confounds_helper(
    confound_raw, strategy=["minimal"], n_components=0.95, motion_model="6params"
):
    """
    Load confounds from fmriprep

    """
    if "nii" not in confound_raw[-6:]:
        confounds_out = _load_confounds_main(
            confound_raw,
            strategy=strategy,
            n_components=n_components,
            motion_model=motion_model,
        )

    else:
        confound_raw = confound_raw.replace(
            "_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz",
            "_desc-confounds_regressors.tsv",
        )
        confounds_out = _load_confounds_main(
            confound_raw,
            strategy=strategy,
            n_components=n_components,
            motion_model=motion_model,
        )
    return confounds_out


def load_confounds(
    confounds_raw, strategy=["minimal"], n_components=0.95, motion_model="6params"
):

    """
    Load confounds from fmriprep

    Parameters

        confounds_raw: Pandas Dataframe or path to tsv file(s)

                       Raw confounds from fmriprep


        strategy: List of strings

                       The strategy used to select a subset of the confounds from fmriprep: each string can be
                       either the name of one of the following subset of confounds or the name of a confound to add.

                       -minimal: basic strategy that uses motion, high pass filter, csf and white matter parameters
                       -motion: ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
                       -high_pass_filter = ["cosine00", "cosine01", ..]
                       -matter: ['csf', 'csf_derivative1_power2', 'csf_derivative1', 'white_matter','white_matter_derivative1_power2', 'white_matter_derivative1',
                       'white_matter_power2', 'csf_power2']
                       -compcor: ["t_comp_cor_00","t_comp_cor_01",..]


        motion_model: String

                Temporal and quadratic terms for head motion estimates

                -6params: standard motion parameters (6)
                -square: standard motion paramters + quadratic terms (12)
                -derivatives: standard motion paramters + derivatives (12)
                -full: standard motion paramteres + derivatives + quadratic terms + squared derivatives (24)


    Returns

        confounds_out:  Pandas DataFrame(s)

                A reduced version of FMRIPREP confounds based on strategy specified by user
    """
    if type(confounds_raw) == str:
        confounds_out = _load_confounds_helper(
            confounds_raw,
            strategy=strategy,
            n_components=n_components,
            motion_model=motion_model,
        )

    elif type(confounds_raw) == list:
        confounds_out = []
        for file in confounds_raw:
            confounds_out.append(
                _load_confounds_helper(
                    file,
                    strategy=strategy,
                    n_components=n_components,
                    motion_model=motion_model,
                )
            )

    else:
        confounds_out = 0
        raise ValueError("Invalid input type")

    return confounds_out
