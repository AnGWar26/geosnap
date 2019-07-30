"""Tools for creating and manipulating neighborhood datasets."""

import os
import zipfile
from warnings import warn
from appdirs import user_data_dir
import matplotlib.pyplot as plt
import pandas as pd
import quilt3
from shapely import wkb, wkt
import geopandas as gpd
import multiprocessing
import sys

sys.path.insert(0,
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyze import cluster as _cluster, cluster_spatial as _cluster_spatial

# look for local storage and create if missing
try:
    from quilt3.data.geosnap_data import storage
except ImportError:
    storage = quilt3.Package()

appname = "geosnap"
appauthor = "geosnap"
data_dir = user_data_dir(appname, appauthor)
if not os.path.exists(data_dir):
    os.mkdir(data_dir)

# get census data from spatialucr quilt account
try:  # if any of these aren't found, the user needs to refresh the quilt data package
    from quilt3.data.census import tracts_cartographic, administrative
except AttributeError:
    warn(
        "Quilt data is outdated... rebuilding\n"
        " You will need to restart your Python kernel once downloading has completed"
    )
    quilt3.Package.install("census/tracts_cartographic", "s3://quilt-cgs")
    quilt3.Package.install("census/administrative", "s3://quilt-cgs")


def _deserialize_wkb(str):
    return wkb.loads(str, hex=True)


def _deserialize_wkt(str):
    return wkt.loads(str)


def convert_gdf(df):
    """Convert DataFrame to GeoDataFrame.

    DataFrame to GeoDataFrame by converting wkt/wkb geometry representation
    back to Shapely object.

    Parameters
    ----------
    df : pandas.DataFrame
        dataframe with column named either "wkt" or "wkb" that stores
        geometric information as well-known text or well-known binary,
        (hex encoded) respectively.

    Returns
    -------
    gpd.GeoDataFrame
        geodataframe with converted `geometry` column.

    """
    df = df.copy()
    df.reset_index(inplace=True, drop=True)

    if "wkt" in df.columns.tolist():
        with multiprocessing.Pool() as P:
            df["geometry"] = P.map(_deserialize_wkt, df["wkt"])
        df = df.drop(columns=["wkt"])

    else:
        with multiprocessing.Pool() as P:
            df["geometry"] = P.map(_deserialize_wkb, df["wkb"])
        df = df.drop(columns=["wkb"])

    df = gpd.GeoDataFrame(df)
    df.crs = {"init": "epsg:4326"}

    return df


def adjust_inflation(df, columns, given_year, base_year=2015):
    """
    Adjust currency data for inflation.

    Parameters
    ----------
    df : DataFrame
        Dataframe of historical data
    columns : list-like
        The columns of the dataframe with currency data
    given_year: int
        The year in which the data were collected; e.g. to convert data from
        the 1990 census to 2015 dollars, this value should be 1990.
    base_year: int, optional
        Constant dollar year; e.g. to convert data from the 1990
        census to constant 2015 dollars, this value should be 2015.
        Default is 2015.

    Returns
    -------
    type
        DataFrame

    """
    # get inflation adjustment table from BLS
    inflation = pd.read_excel(
        "https://www.bls.gov/cpi/research-series/allitems.xlsx", skiprows=6)
    inflation.columns = inflation.columns.str.lower()
    inflation.columns = inflation.columns.str.strip(".")
    inflation = inflation.dropna(subset=["year"])
    inflator = inflation.groupby("year")["avg"].first().to_dict()
    inflator[1970] = 63.9

    df = df.copy()
    updated = df[columns].apply(lambda x: x *
                                (inflator[base_year] / inflator[given_year]))
    df.update(updated)

    return df


class DataStore(object):
    """Storage for geosnap data. Currently supports US Census data."""
    def __init__(self):
        self

    def tracts_1990(self, convert=True):
        """Nationwide Census Tracts as drawn in 1990 (cartographic 500k).

        Parameters
        ----------
        convert : bool
            if True, return geodataframe, else return dataframe (the default is True).

        Returns
        -------
        pandas.DataFrame or geopandas.GeoDataFrame.
            1990 tracts as a geodataframe or as a dataframe with geometry
            stored as well-known binary on the 'wkb' column.

        """
        t = tracts_cartographic["tracts_1990_500k.parquet"]()
        t["year"] = 1990
        if convert:
            return convert_gdf(t)
        else:
            return t

    def tracts_2000(self, convert=True):
        """Nationwide Census Tracts as drawn in 2000 (cartographic 500k).

        Parameters
        ----------
        convert : bool
            if True, return geodataframe, else return dataframe (the default is True).

        Returns
        -------
        pandas.DataFrame.
            2000 tracts as a geodataframe or as a dataframe with geometry
            stored as well-known binary on the 'wkb' column.

        """
        t = tracts_cartographic["tracts_2000_500k.parquet"]()
        t["year"] = 2000
        if convert:
            return convert_gdf(t)
        else:
            return t

    def tracts_2010(self, convert=True):
        """Nationwide Census Tracts as drawn in 2010 (cartographic 500k).

        Parameters
        ----------
        convert : bool
            if True, return geodataframe, else return dataframe (the default is True).

        Returns
        -------
        pandas.DataFrame.
            2010 tracts as a geodataframe or as a dataframe with geometry
            stored as well-known binary on the 'wkb' column.

        """
        t = tracts_cartographic["tracts_2010_500k.parquet"]()
        t["year"] = 2010
        if convert:
            return convert_gdf(t)
        else:
            return t

    def msas(self, convert=True):
        """Metropolitan Statistical Areas as drawn in 2010.

        Parameters
        ----------
        convert : bool
            if True, return geodataframe, else return dataframe (the default is True).

        Returns
        -------
        geopandas.GeoDataFrame.
            2010 MSAs as a geodataframe or as a dataframe with geometry
            stored as well-known binary on the 'wkb' column.

        """
        if convert:
            return convert_gdf(administrative["msas.parquet"]())
        else:
            return administrative["msas.parquet"]()

    def states(self, convert=True):
        """States.

        Parameters
        ----------
        convert : bool
            if True, return geodataframe, else return dataframe (the default is True).

        Returns
        -------
        geopandas.GeoDataFrame.
            US States as a geodataframe or as a dataframe with geometry
            stored as well-known binary on the 'wkb' column.

        """
        if convert:
            return convert_gdf(administrative["states.parquet"]())
        else:
            return administrative["states.parquet"]()

    def counties(self, convert=True):
        """Nationwide counties as drawn in 2010.

        Parameters
        ----------
        convert : bool
            if True, return geodataframe, else return dataframe (the default is True).

        Returns
        -------
        geopandas.GeoDataFrame.
            2010 counties as a geodataframe or as a dataframe with geometry
            stored as well-known binary on the 'wkb' column.

        """
        return convert_gdf(administrative["counties.parquet"]())

    @property
    def msa_definitions(self):
        """2010 Metropolitan Statistical Area definitions.

        Returns
        -------
        pandas.DataFrame.
            dataframe that stores state/county --> MSA crosswalk definitions.

        """
        return administrative["msa_definitions.parquet"]()

    @property
    def ltdb(self):
        """Longitudinal Tract Database (LTDB).

        Returns
        -------
        pandas.DataFrame or geopandas.GeoDataFrame
            LTDB as a long-form geo/dataframe

        """
        try:
            return storage["ltdb"]()
        except KeyError:
            print("Unable to locate LTDB data. Try saving the data again "
                  "using the `store_ltdb` function")

    @property
    def ncdb(self):
        """Geolytics Neighborhood Change Database (NCDB).

        Returns
        -------
        pandas.DataFrarme
            NCDB as a long-form dataframe

        """
        try:
            return storage["ncdb"]()
        except KeyError:
            print("Unable to locate NCDB data. Try saving the data again "
                  "using the `store_ncdb` function")

    @property
    def codebook(self):
        """Codebook.

        Returns
        -------
        pandas.DataFrame.
            codebook that stores variable names, definitions, and formulas.

        """
        return pd.read_csv(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "variables.csv"))


data_store = DataStore()


def store_ltdb(sample, fullcount):
    """
    Read & store data from Brown's Longitudinal Tract Database (LTDB).

    Parameters
    ----------
    sample : str
        file path of the zip file containing the standard Sample CSV files
        downloaded from
        https://s4.ad.brown.edu/projects/diversity/Researcher/LTBDDload/Default.aspx

    fullcount: str
        file path of the zip file containing the standard Fullcount CSV files
        downloaded from
        https://s4.ad.brown.edu/projects/diversity/Researcher/LTBDDload/Default.aspx

    Returns
    -------
    pandas.DataFrame

    """
    sample_zip = zipfile.ZipFile(sample)
    fullcount_zip = zipfile.ZipFile(fullcount)

    def _ltdb_reader(path, file, year, dropcols=None):

        df = pd.read_csv(
            path.open(file),
            na_values=["", " ", 99999, -999],
            converters={
                0: str,
                "placefp10": str
            },
            low_memory=False,
            encoding="latin1",
        )

        if dropcols:
            df.drop(dropcols, axis=1, inplace=True)
        df.columns = df.columns.str.lower()
        names = df.columns.values.tolist()
        names[0] = "geoid"
        newlist = []

        # ignoring the first 4 columns, remove year suffix from column names
        for name in names[4:]:
            newlist.append(name[:-2])
        colnames = names[:4] + newlist
        df.columns = colnames

        # prepend a 0 when FIPS is too short
        df["geoid"] = df["geoid"].str.rjust(11, "0")
        df.set_index("geoid", inplace=True)

        df["year"] = year

        inflate_cols = [
            "mhmval",
            "mrent",
            "incpc",
            "hinc",
            "hincw",
            "hincb",
            "hinch",
            "hinca",
        ]

        inflate_available = list(
            set(df.columns).intersection(set(inflate_cols)))

        if len(inflate_available):
            # try:
            df = adjust_inflation(df, inflate_available, year)
        # except KeyError:  # half the dfs don't have these variables
        #     pass
        return df

    # read in Brown's LTDB data, both the sample and fullcount files for each
    # year population, housing units & occupied housing units appear in both
    # "sample" and "fullcount" files-- currently drop sample and keep fullcount

    sample70 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_1970_sample.csv",
        dropcols=["POP70SP1", "HU70SP", "OHU70SP"],
        year=1970,
    )

    fullcount70 = _ltdb_reader(fullcount_zip,
                               "LTDB_Std_1970_fullcount.csv",
                               year=1970)

    sample80 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_1980_sample.csv",
        dropcols=["pop80sf3", "pop80sf4", "hu80sp", "ohu80sp"],
        year=1980,
    )

    fullcount80 = _ltdb_reader(fullcount_zip,
                               "LTDB_Std_1980_fullcount.csv",
                               year=1980)

    sample90 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_1990_sample.csv",
        dropcols=["POP90SF3", "POP90SF4", "HU90SP", "OHU90SP"],
        year=1990,
    )

    fullcount90 = _ltdb_reader(fullcount_zip,
                               "LTDB_Std_1990_fullcount.csv",
                               year=1990)

    sample00 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_2000_sample.csv",
        dropcols=["POP00SF3", "HU00SP", "OHU00SP"],
        year=2000,
    )

    fullcount00 = _ltdb_reader(fullcount_zip,
                               "LTDB_Std_2000_fullcount.csv",
                               year=2000)

    sample10 = _ltdb_reader(sample_zip,
                            "ltdb_std_all_sample/ltdb_std_2010_sample.csv",
                            year=2010)

    # join the sample and fullcount variables into a single df for the year
    ltdb_1970 = sample70.drop(columns=["year"]).join(fullcount70.iloc[:, 7:],
                                                     how="left")
    ltdb_1980 = sample80.drop(columns=["year"]).join(fullcount80.iloc[:, 7:],
                                                     how="left")
    ltdb_1990 = sample90.drop(columns=["year"]).join(fullcount90.iloc[:, 7:],
                                                     how="left")
    ltdb_2000 = sample00.drop(columns=["year"]).join(fullcount00.iloc[:, 7:],
                                                     how="left")
    ltdb_2010 = sample10

    df = pd.concat([ltdb_1970, ltdb_1980, ltdb_1990, ltdb_2000, ltdb_2010],
                   sort=True)

    renamer = dict(
        zip(
            data_store.codebook["ltdb"].tolist(),
            data_store.codebook["variable"].tolist(),
        ))

    df.rename(renamer, axis="columns", inplace=True)

    # compute additional variables from lookup table
    for row in data_store.codebook["formula"].dropna().tolist():
        df.eval(row, inplace=True)

    keeps = df.columns[df.columns.isin(
        data_store.codebook["variable"].tolist() + ["year"])]
    df = df[keeps]

    df.to_parquet(os.path.join(data_dir, "ltdb.parquet"), compression="brotli")
    storage.set("ltdb", os.path.join(data_dir, "ltdb.parquet"))
    storage.build("geosnap_data/storage")


def store_ncdb(filepath):
    """
    Read & store data from Geolytics's Neighborhood Change Database.

    Parameters
    ----------
    filepath : str
        location of the input CSV file extracted from your Geolytics DVD

    """
    ncdb_vars = data_store.codebook["ncdb"].dropna()[1:].values

    names = []
    for name in ncdb_vars:
        for suffix in ["7", "8", "9", "0", "1", "2"]:
            names.append(name + suffix)
    names.append("GEO2010")

    c = pd.read_csv(filepath, nrows=1).columns
    c = pd.Series(c.values)

    keep = []
    for i, col in c.items():
        for name in names:
            if col.startswith(name):
                keep.append(col)

    df = pd.read_csv(
        filepath,
        usecols=keep,
        engine="c",
        na_values=["", " ", 99999, -999],
        converters={
            "GEO2010": str,
            "COUNTY": str,
            "COUSUB": str,
            "DIVISION": str,
            "REGION": str,
            "STATE": str,
        },
    )

    cols = df.columns
    fixed = []
    for col in cols:
        if col.endswith("D"):
            fixed.append("D" + col[:-1])
        elif col.endswith("N"):
            fixed.append("N" + col[:-1])
        elif col.endswith("1A"):
            fixed.append(col[:-2] + "2")

    orig = []
    for col in cols:
        if col.endswith("D"):
            orig.append(col)
        elif col.endswith("N"):
            orig.append(col)
        elif col.endswith("1A"):
            orig.append(col)

    renamer = dict(zip(orig, fixed))
    df.rename(renamer, axis="columns", inplace=True)

    df = df[df.columns[df.columns.isin(names)]]

    df = pd.wide_to_long(df,
                         stubnames=ncdb_vars,
                         i="GEO2010",
                         j="year",
                         suffix="(7|8|9|0|1|2)").reset_index()

    df["year"] = df["year"].replace({
        7: 1970,
        8: 1980,
        9: 1990,
        0: 2000,
        1: 2010,
        2: 2010
    })
    df = df.groupby(["GEO2010", "year"]).first()

    mapper = dict(zip(data_store.codebook.ncdb, data_store.codebook.variable))

    df.reset_index(inplace=True)

    df = df.rename(mapper, axis="columns")

    df = df.set_index("geoid")

    for row in data_store.codebook["formula"].dropna().tolist():
        try:
            df.eval(row, inplace=True)
        except:
            warn("Unable to compute " + str(row))

    keeps = df.columns[df.columns.isin(
        data_store.codebook["variable"].tolist() + ["year"])]

    df = df[keeps]

    df = df.loc[df.n_total_pop != 0]

    df.to_parquet(os.path.join(data_dir, "ncdb.parquet"), compression="brotli")
    storage.set("ncdb", os.path.join(data_dir, "ncdb.parquet"))
    storage.build("geosnap_data/storage")


def get_lehd(dataset="wac", state="dc", year=2015):
    """Grab data from the LODES FTP server as a pandas DataFrame.

    Parameters
    ----------
    dataset : str
        which LODES dataset to collect: "rac" or wac", reffering to either
        residence area characteristics or workplace area characteristics
        the default is 'wac').
    state : str
        two-digit state abbreviation for example "ca" or "OH"
    year : str
        which year to collect. First year avaialable for most states is 2002.
        Consult the LODES documentation for more details. The default is 2015.

    Returns
    -------
    pandas.DataFrame
        a pandas DataFrame with columns representing census blocks, indexed on
        the block FIPS code.

    """
    state = state.lower()
    url = "https://lehd.ces.census.gov/data/lodes/LODES7/{state}/{dataset}/{state}_{dataset}_S000_JT00_{year}.csv.gz".format(
        dataset=dataset, state=state, year=year)
    df = pd.read_csv(url, converters={"w_geocode": str, "h_geocode": str})
    df = df.rename({"w_geocode": "geoid", "h_geocode": "geoid"}, axis=1)
    df = df.set_index("geoid")

    return df


def _fips_filter(state_fips=None,
                 county_fips=None,
                 msa_fips=None,
                 fips=None,
                 data=None):

    if isinstance(state_fips, (str, )):
        state_fips = [state_fips]
    if isinstance(county_fips, (str, )):
        county_fips = [county_fips]
    if isinstance(fips, (str, )):
        fips = [fips]

    # if counties already present in states, ignore them
    if county_fips:
        for i in county_fips:
            if state_fips and i[:2] in county_fips:
                county_fips.remove(i)
    # if any fips present in state or counties, ignore them too
    if fips:
        for i in fips:
            if state_fips and i[:2] in state_fips:
                fips.remove(i)
            if county_fips and i[:5] in county_fips:
                fips.remove(i)

    fips_list = []
    if fips:
        fips_list += fips
    if county_fips:
        fips_list += county_fips
    if state_fips:
        fips_list += state_fips

    if msa_fips:
        fips_list += data_store.msa_definitions[
            data_store.msa_definitions["CBSA Code"] ==
            msa_fips]["stcofips"].tolist()

    dfs = []
    for index in fips_list:
        dfs.append(data[data.geoid.str.startswith(index)])

    return pd.concat(dfs)


def _from_db(data,
             state_fips=None,
             county_fips=None,
             msa_fips=None,
             fips=None,
             years=None):

    data = data[data.year.isin(years)]
    data = data.reset_index()

    df = _fips_filter(
        state_fips=state_fips,
        county_fips=county_fips,
        msa_fips=msa_fips,
        fips=fips,
        data=data,
    )

    # we know we're using 2010, need to drop the year column so no conficts
    tracts = data_store.tracts_2010(convert=False)
    tracts = tracts[["geoid", "wkb"]]
    tracts = tracts[tracts.geoid.isin(df.geoid)]
    tracts = convert_gdf(tracts)

    gdf = df.merge(tracts, on="geoid", how="left").set_index("geoid")
    gdf = gpd.GeoDataFrame(gdf)
    return gdf


class Community(object):
    """Spatial and tabular data for a collection of "neighborhoods".

       A community is a collection of "neighborhoods" represented by spatial
       boundaries (e.g. census tracts, or blocks in the US), and tabular data
       which describe the composition of each neighborhood (e.g. data from
       surveys, sensors, or geocoded misc.). A Community can be large (e.g. a
       metropolitan region), or small (e.g. a handfull of census tracts) and
       may have data pertaining to multiple discrete points in time.

     """
    def __init__(self, gdf=None, harmonized=None, **kwargs):
        """initialize Community.

        Parameters
        ----------
        gdf : geopandas.GeoDataFrame
            long-form geodataframe that stores neighborhood-level attributes
            and geometries for one or more time periods
        harmonized : bool
            Whether neighborhood boundaries have been harmonized into
            consistent units over time
        **kwargs : type
            Description of parameter `**kwargs`.

        Returns
        -------
        type
            Description of returned object.

        Examples
        -------
        Examples should be written in doctest format, and
        should illustrate how to use the function/class.
        >>>

        """
        self.gdf = gdf
        if harmonized:
            self.harmonized = True

    def cluster(self,
                n_clusters=6,
                method=None,
                best_model=False,
                columns=None,
                verbose=False,
                **kwargs):
        self.gdf = _cluster(gdf=self.gdf,
                            n_clusters=n_clusters,
                            method=method,
                            best_model=best_model,
                            columns=columns,
                            verbose=verbose,
                            **kwargs)

    def cluster_spatial(self,
                        n_clusters=6,
                        weights_type="rook",
                        method=None,
                        best_model=False,
                        columns=None,
                        threshold_variable="count",
                        threshold=10,
                        **kwargs):
        self.gdf = _cluster_spatial(gdf=self.gdf,
                                    n_clusters=n_clusters,
                                    weights_type=weights_type,
                                    method=method,
                                    best_model=best_model,
                                    columns=columns,
                                    threshold_variable=threshold_variable,
                                    threshold=threshold,
                                    **kwargs)

    @classmethod
    def from_ltdb(
            cls,
            state_fips=None,
            county_fips=None,
            msa_fips=None,
            fips=None,
            years=[1970, 1980, 1990, 2000, 2010],
    ):

        gdf = _from_db(
            data=data_store.ltdb,
            state_fips=state_fips,
            county_fips=county_fips,
            msa_fips=msa_fips,
            fips=fips,
            years=years,
        )

        return cls(gdf=gdf, harmonized=True)

    @classmethod
    def from_ncdb(
            cls,
            state_fips=None,
            county_fips=None,
            msa_fips=None,
            fips=None,
            years=[1970, 1980, 1990, 2000, 2010],
    ):

        gdf = _from_db(
            data=data_store.ltdb,
            state_fips=state_fips,
            county_fips=county_fips,
            msa_fips=msa_fips,
            fips=fips,
            years=years,
        )

        return cls(gdf=gdf, harmonized=True)
