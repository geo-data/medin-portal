var map;            // map object

// top level function to initialise the map
function init_map() {
    var extent = new OpenLayers.Bounds(-180, -90, 180, 90);
    var options = {
        restrictedExtent: extent,
        maxExtent: extent,
        maxResolution: 360/512,
        controls: []            // we will add our own controls
    }

    map = new OpenLayers.Map('map', options); // assign the map to the global variable

    // add the bathymetry layer
    var layer = new OpenLayers.Layer.TMS( "Bathy",
                                      script_root+'/spatial/tms/',
                                      { layername: 'bathymetry',
                                        type: 'png',
                                        displayInLayerSwitcher: false } );
    map.addLayer(layer);

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
                                          });
    map.addLayer(layer);

    // add the ICES rectangles layer. This is a subset of data from the DASS WFS
    styleMap = new OpenLayers.StyleMap({
        'default': OpenLayers.Util.applyDefaults(
            {
                label: '${Name}', // ${dassh:ICESNAME} when using DASSH WFS
                fontColor: '#72721E',
                strokeWidth:1,
                strokeColor:"#7C7B52",
                fillColor: "yellow",
                fillOpacity: 0.25
            })
    });

    layer = new OpenLayers.Layer.GML( "ICES Rectangles",
                                      '/data/ices-rectangles/areas.geojson',
                                      {
                                          styleMap: styleMap,
                                          format: OpenLayers.Format.GeoJSON,
                                          visibility: false,
                                          minScale: 3500000
                                      });
    /* OpenLayers in FireFox doesn't seem to like the DASSH WFS
    layer = new OpenLayers.Layer.WFS( "ICES Rectangles",
                                      "http://www.dassh.ac.uk:8081/geoserver/wfs?",
                                      {
                                          typename: "dassh:ices_squares_simple",
                                          maxfeatures: 100
                                      },
                                      {
                                          featureClass: OpenLayers.Feature.WFS,
                                          minScale: 3500000,
                                          styleMap: styleMap
                                      });*/
    map.addLayer(layer);

    // default controls
    var nav = new OpenLayers.Control.Navigation();
    map.addControl(nav);
    map.addControl(new OpenLayers.Control.PanZoom());
    map.addControl(new OpenLayers.Control.ArgParser());
    map.addControl(new OpenLayers.Control.Attribution());

    // the graticule layer
    map.addControl(new OpenLayers.Control.Graticule({
        numPoints: 2, 
        labelled: true,
        visible: true
    }));

    map.addControl(new OpenLayers.Control.MousePosition());

    return nav;
}
