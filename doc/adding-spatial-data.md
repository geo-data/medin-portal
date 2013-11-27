# Adding Spatial Data to the Portal

This document provides technical instructions on how to add spatial data to the
MEDIN Portal.  Spatial data is used in the Geographic Search interface on the
Search page.  It is used to drive two elements of the Geographic interface:

- The contextual layers that are visible on the OpenLayers map and selectable
  using the legend (e.g. ICES Rectangles).

- The dropdown boxes which specify pre-defined bounding boxes used in searches
  (e.g. Countries).

Although this document only deals with adding data, steps for removing or
editing data can be logically derived from it.

The following instructions assume you are working in a local checkout of the
project git repository and commit your changes accordingly.

## Adding a contextual map layer

Creating a contextual layer for display within the OpenLayers map only requires
editing and creating files consumed by the browser: there is no need to edit
server side code. This achieved by the following steps:

1. Obtain a GeoJSON file representing a GeoJSON `FeatureCollection` of the new
   spatial data.  If you require a feature to have an associated label rendered
   on the map then ensure that the feature has a property called `Name` with an
   appropriate value which to be used as the label.  By convention this file
   should be called `areas.geojson`.
   
2. `areas.geojson` needs to be served up to OpenLayers when required.  This can
   be achieved by creating an appropriate directory beneath `html/data`
   (e.g. `html/data/my-new-layer`) and placing `areas.geojson` within it.

3. Make OpenLayers aware of the new data.  This involves editing the function
   `init_map()` in the file `html/js/full/map.js`.  An example explains this
   most clearly - the following code is all that is required to add the UK
   Charting Progress Sea Areas.  Simply ensure that
   `/data/charting-progress/areas.geojson` is changed to
   `/data/my-new-layer/areas.geojson` and edit the name and any other styling
   or layer options to suit your requirements.

```javascript
    // add the UK Charting Progress Sea Areas
    var styleMap = new OpenLayers.StyleMap({
        'default': OpenLayers.Util.applyDefaults(
            {
                label: '${Name}',
                fontColor: '#1E2772',
                strokeWidth:1,
                strokeColor:"#52577C",
                fillColor: "blue",
                fillOpacity: 0.25
            })
    });

    var layer = new OpenLayers.Layer.GML( "UK Charting Progress Sea Areas",
                                          '/data/charting-progress/areas.geojson',
                                          {
                                              styleMap: styleMap,
                                              visibility: false,
                                              format: OpenLayers.Format.GeoJSON
                                              //, minscale: 3500000
                                          });
    map.addLayer(layer);
```

The new layer should now be available once the changes are committed and
deployed.

When in doubt use the existing layers as a template for adding your new data.

# Adding data to the area dropdown controls

This is more involved than adding data to the map and requires the following
server side changes: adding bounding box data to a sqlite database; editing the
Portal's spatial Python module to hook into that data; editing the search view
to make use of the new spatial hooks; and finally editing the HTML template to
render the variables exposed by the hooks into the dropdown controls.  In more
detail these steps are as follows:

1. The bounding box data is stored in `data/portal.sqlite` in tables that must
   have a specific structure describing the bounding box id, name and
   coordinates.  This structure is exemplified by the `ices_rectangles` table:

```sql
CREATE TABLE "ices_rectangles" (
       id varchar(4) PRIMARY KEY,
       name varchar(255) UNIQUE NOT NULL,
       minx double NOT NULL,
       miny double NOT NULL,
       maxx double NOT NULL,
       maxy double NOT NULL
);
```

Note that the `id` data type can be any length of varchar that is required.

The table name can be any name that is not already taken and makes sense for
your data e.g. `my_new_data`.

As well as creating and populating this table, the `areas` view must also be
updated to include the new bounding boxes.  This view is used when performing
bounding box queries that are abstracted from the source of the data.  The view
is along the lines of:

```sql
CREATE VIEW areas AS
  SELECT id, name, minx, miny, maxx, maxy, 'co' AS type FROM countries
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'co' AS type FROM british_isles
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'sa' AS type FROM sea_areas
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'cp' AS type FROM charting_progress_areas
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'ir' AS type FROM ices_rectangles;
```

After adding your new table it should look something like:

```sql
CREATE VIEW areas AS
  SELECT id, name, minx, miny, maxx, maxy, 'co' AS type FROM countries
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'co' AS type FROM british_isles
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'sa' AS type FROM sea_areas
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'cp' AS type FROM charting_progress_areas
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'ir' AS type FROM ices_rectangles
  UNION
  SELECT id, name, minx, miny, maxx, maxy, 'nd' AS type FROM my_new_data;
```

The `nd` value specified for the `type` field is used as key in the dropdowns
to differentiate between the data source: choose an appropriate value and
remember it - it will be used in future steps.

2. Edit the `Areas` class in `python/medin/spatial.py` to hook into the new
   database table. This involves creating a new method on this class that
   retrieves the id and name for the new table.  Again the method to obtain
   ICES Rectangles provides a good template:
   
```python
    def icesRectangles(self):
        cur = self._db.cursor()
        cur.execute('SELECT id, name FROM ices_rectangles')
        return [row for row in cur]
```

This just needs to be renamed (e.g. to `myNewData()` and have the
`ices_rectangles` table name replaced with `my_new_data` to continue the
example.

3. The Search view now needs to be edited to make use of the new spatial
   method, which is called to add the associated id and name tuples to the
   search template.  Specifically, the definition for the `area_ids` hash in
   the `setup()` method of the `Search` class needs to be updated.  This is
   found in `python/medin/views.py`. As an example it may be defined along the
   following lines:
   
```python
        area_ids = {'british-isles': areas.britishIsles(),
                    'countries': areas.countries(),
                    'sea-areas': areas.seaAreas(),
                    'progress-areas': areas.chartingProgressAreas(),
                    'ices-rectangles': areas.icesRectangles()}
```

Editing it to include the new data method would be along these lines:

```python
        area_ids = {'british-isles': areas.britishIsles(),
                    'countries': areas.countries(),
                    'sea-areas': areas.seaAreas(),
                    'progress-areas': areas.chartingProgressAreas(),
                    'ices-rectangles': areas.icesRectangles(),
                    'my-new-data': areas.myNewData()}
```

Note that the `my-new-data` key to `area_ids` will be used in the template to
reference the new data.

4. The `templates/full/search.html` Mako template now needs to be edited to
   extend the dropdowns to incorporate the new data.  This firstly involves
   editing the `for` loop in the area type select dropdown (found with the
   string `<select name="t" id="area-type">`).  Using our example the `for`
   loop should end up looking as follows:
   
```python
%for id, name in (('co', 'Countries'), ('sa', 'SeaVoX Salt and Fresh Water Body Gazetteer'), ('cp', 'UK Charting Progress Sea Areas'), ('ir', 'ICES Rectangles'), ('nd', 'My New Data')):
```

Note that the `nd` identifier specified in the sqlite `areas` view in step 1 is
used here.

Next the select dropdown containing the names for the new bounding boxes should
be appended to the other selects.  Our example would be:

```html
        <select class="area" id="nd"\
          %if area_type == 'nd':
 name="a"\
          %else:
 style="display: none"\
          %endif
>
          <option value="">Select a new area...</option>
${area_selection('my-new-data')}
        </select>
```

Again this uses the `nd` identifier, this time to determine whether to display
the dropdown on page load.  It also uses the `my-new-data` identifier which is
passed to the Mako `area_selection()` function to build the options
representing the new data.

Committing and deploying these changes  should result in your new data dropdown
being ready for use.
