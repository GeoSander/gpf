# coding: utf-8

# Copyright (c) 2019 | MIT License | Geocom Informatik AG, Burgdorf, Switzerland

"""
The *geometry* module contains functions that help construct Esri geometries.
"""
import gpf.common.iterutils as _iter
import gpf.common.textutils as _tu
import gpf.common.validate as _vld
from gpf.tools import arcpy as _arcpy


class GeometryError(ValueError):
    """ If the :class:`ShapeBuilder` cannot create the desired output geometry, a GeometryError is raised. """
    pass


class ShapeBuilder(object):
    """
    Helper class to construct Esri geometry objects from arcpy ``Point`` or ``Array`` objects or coordinate values.

        Examples:

            >>> # instantiate a 2D PointGeometry
            >>> ShapeBuilder(6.5, 2.8).as_point()
            <PointGeometry object at 0x19fcbdf0[0x19fcbd80]>

            >>> # instantiate a 3D PointGeometry
            >>> ShapeBuilder(6.5, 2.8, 5.3).as_point(has_z=True)
            <PointGeometry object at 0x6b96210[0x19fcbbe0]>

            >>> # construct a 2D line (append technique)
            >>> shp = ShapeBuilder()
            >>> shp.append(1.0, 2.0)
            >>> shp.append(1.5, 3.0)
            >>> shp.as_polyline()
            <Polyline object at 0x6a9bb70[0x6fe2540]>

            >>> # construct a 3D polygon from 2D coordinates
            >>> shp = ShapeBuilder([(1.0, 2.0), (1.5, 3.0), (2.0, 2.0)])
            >>> polygon = shp.as_polygon(has_z=True)
            >>> # Z values are added and set to 0
            >>> polygon.firstPoint
            <Point (1.00012207031, 2.00012207031, 0.0, #)>
            >>> # note that the "open" polygons will be closed automatically
            >>> polygon.firstPoint == polygon.lastPoint
            True
            >>> # calling as_point() on a ShapeBuilder with multiple coordinates will return a centroid
            >>> shp.as_point()
            <Point (1.50012207031, 2.33345540365, #, #)>
    """

    __slots__ = '_arr', '_num_coords'

    def __init__(self, *args):
        # Because Array is an ArcObject, we cannot inherit from it the way we'd like to (raises RuntimeError).
        # We'll instantiate a new Array and store it in its own variable instead...
        self._arr = _arcpy.Array()
        self._num_coords = 0
        if args:
            try:
                self.extend(_iter.first(args))
            except ValueError:
                self.append(*args)

    def __iter__(self):
        return iter(self._arr)

    def __len__(self):
        return len(self._arr)

    def append(self, *args):
        """
        Adds a coordinate or coordinate array to the geometry.
        Valid objects are another ``ShapeBuilder`` instance, an ArcPy ``Point`` or ``Array`` instance,
        or numeric X, Y, (Z, M, ID) values.

        :param args:        A valid coordinate object.
        :type args:         float, int, arcpy.Point, arcpy.Array, ShapeBuilder
        :raises ValueError: If the coordinate object is invalid and cannot be added.

        .. seealso::    https://desktop.arcgis.com/en/arcmap/latest/analyze/arcpy-classes/point.htm
        """
        value = tuple(_iter.collapse(args, levels=1))
        try:
            if len(value) == 1:
                # User can add Point, Array or ShapeBuilder objects
                coord = _iter.first(value)
                if isinstance(coord, (ShapeBuilder, _arcpy.Array)):
                    self._arr.append(coord)
                    self._num_coords += coord.num_coords if hasattr(coord, 'num_coords') else len(coord)
                    return
            elif 2 <= len(value) <= 5:
                # User can add up to 5 values (X, Y, Z, M, ID)
                coord = _arcpy.Point(*value)
            else:
                raise ValueError('Cannot add coordinate object {}'.format(_tu.to_repr(value)))
            self._arr.append(coord)
            self._num_coords += 1
        except (RuntimeError, ValueError) as e:
            # User tried to add something invalid
            raise ValueError(e)

    def extend(self, values):
        """
        Adds multiple coordinates to the geometry.

        :param values:      An iterable of numeric coordinate values, ``Point``, ``Array`` or ``ShapeBuilder`` objects.
        :type values:       tuple, list
        :raises ValueError: If the *values* argument is not an iterable.
        """
        _vld.pass_if(_vld.is_iterable(values), ValueError, 'extend() expects an iterable')
        for v in values:
            self.append(v)

    @staticmethod
    def _output(shape_type, coords, spatial_reference, has_z, has_m):
        """ Outputs the stored geometry array as the specified type. """
        try:
            return shape_type(coords, spatial_reference, has_z, has_m)
        except Exception as e:
            raise GeometryError(e)

    @property
    def num_coords(self):
        """
        Returns the total number of coordinates in the ShapeBuilder.
        Note that this does not always return the same value as calling :func:`len` on the ShapeBuilder,
        because :func:`num_coords` also counts the coordinates in nested geometry arrays.

        :rtype: int
        """
        return self._num_coords

    def as_point(self, spatial_reference=None, has_z=False, has_m=False):
        """
        Returns the constructed geometry as an Esri ``PointGeometry``.
        Note that if the ShapeBuilder holds more than 1 coordinate, a centroid point is returned.

        :param spatial_reference:   An optional spatial reference. Defaults to 'Unknown'.
        :param has_z:               If ``True``, the geometry is Z aware. Defaults to ``False``.
        :param has_m:               If ``True``, the geometry is M aware. Defaults to ``False``.
        :type spatial_reference:    str, unicode, int, arcpy.SpatialReference
        :type has_z:                bool
        :type has_m:                bool
        :rtype:                     arcpy.PointGeometry
        :raises GeometryError:      If there is less than 1 coordinate.
        """
        _vld.pass_if(self.num_coords >= 1, GeometryError, 'PointGeometry must have at least 1 coordinate')
        if self.num_coords == 1:
            return self._output(_arcpy.PointGeometry, self._arr[0], spatial_reference, has_z, has_m)
        else:
            return self._output(_arcpy.Multipoint, self._arr, spatial_reference, has_z, has_m).centroid

    def as_multipoint(self, spatial_reference=None, has_z=False, has_m=False):
        """
        Returns the constructed geometry as an Esri ``Multipoint``.

        :param spatial_reference:   An optional spatial reference. Defaults to 'Unknown'.
        :param has_z:               If ``True``, the geometry is Z aware. Defaults to ``False``.
        :param has_m:               If ``True``, the geometry is M aware. Defaults to ``False``.
        :type spatial_reference:    str, unicode, int, arcpy.SpatialReference
        :type has_z:                bool
        :type has_m:                bool
        :rtype:                     arcpy.Multipoint
        :raises GeometryError:      If there are less than 2 coordinates.
        """
        _vld.pass_if(self.num_coords >= 2, GeometryError, 'Multipoint must have at least 2 coordinates')
        return self._output(_arcpy.Multipoint, self._arr, spatial_reference, has_z, has_m)

    def as_polyline(self, spatial_reference=None, has_z=False, has_m=False):
        """
        Returns the constructed geometry as an Esri ``Polyline``.

        :param spatial_reference:   An optional spatial reference. Defaults to 'Unknown'.
        :param has_z:               If ``True``, the geometry is Z aware. Defaults to ``False``.
        :param has_m:               If ``True``, the geometry is M aware. Defaults to ``False``.
        :type spatial_reference:    str, unicode, int, arcpy.SpatialReference
        :type has_z:                bool
        :type has_m:                bool
        :rtype:                     arcpy.Polyline
        :raises GeometryError:      If there are less than 2 coordinates.
        """
        _vld.pass_if(self.num_coords >= 2, GeometryError, 'Polyline must have at least 2 coordinates')
        return self._output(_arcpy.Polyline, self._arr, spatial_reference, has_z, has_m)

    def as_polygon(self, spatial_reference=None, has_z=False, has_m=False):
        """
        Returns the constructed geometry as an Esri ``Polygon``.
        If the polygon is not closed, the first coordinate will be added as the last coordinate automatically
        in order to properly close it.

        :param spatial_reference:   An optional spatial reference. Defaults to 'Unknown'.
        :param has_z:               If ``True``, the geometry is Z aware. Defaults to ``False``.
        :param has_m:               If ``True``, the geometry is M aware. Defaults to ``False``.
        :type spatial_reference:    str, unicode, int, arcpy.SpatialReference
        :type has_z:                bool
        :type has_m:                bool
        :rtype:                     arcpy.Polygon
        :raises ValueError:         If there are less than 3 coordinates.
        """
        _vld.pass_if(self.num_coords >= 3, GeometryError, 'Polygon must have at least 3 coordinates')
        coords = self._arr
        if self.num_coords == 3:
            # Use a copy of the current array and append the first point to close the polygon
            coords = _arcpy.Array(c for c in self._arr)
            coords.append(self._arr[0])
        return self._output(_arcpy.Polygon, coords, spatial_reference, has_z, has_m)
