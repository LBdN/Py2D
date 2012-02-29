"""Calculation of polygonal Field of View (FOV)"""

import Math

class Vision:
	"""Class for representing a polygonal field of vision (FOV)."""
	def __init__(self, obstructors):
		"""Create a new vision object.

		@type obstructors: list
		@param obstructors: A list of obstructors. Obstructors are a list of vectors, so this should be a list of lists.
		"""

		self.set_obstructors(obstructors)
		self.debug = False


		self.debug_points = []

	def set_obstructors(self, obstructors):
		"""Set new obstructor data for the Vision object.
	
		This will also cause the vision polygon to become invalidated, resulting in a re-calculation the next time you access it.

		@type obstructors: list
		@param obstructors: A list of obstructors. Obstructors are a list of vectors, so this should be a list of lists.
		"""
		def flatten_list(l):
			if l:
				return reduce(lambda x,y: x+y, l)
			else:
				return []

		# concatenate list of lists of vectors to a list of vectors
		self.obs_points = flatten_list(obstructors)			
		
		# convert obstructor line strips to lists of line segments
		self.obs_segs = flatten_list([ zip(strip, strip[1:]) for strip in obstructors ])

		self.cached_vision = None
		self.cached_position = None
		self.cached_radius = None

	def get_vision(self, eye, radius, boundary):
		"""Get a vision polygon for a given eye position and boundary Polygon.
		
		@type eye: Vector
		@param eye: The position of the viewer (normally the center of the boundary polygon)
		@type radius: float
		@param radius: The maximum vision radius (normally the radius of the boundary polygon)
		@type boundary: Polygon
		@param boundary: The boundary polygon that describes the maximal field of vision
		"""

		if self.cached_vision == None or (self.cached_position - eye).get_length_squared() > 1:
			self.calculate(eye, radius, boundary)

		return self.cached_vision


	def calculate(self, eye, radius, boundary):
		"""Re-calculate the vision polygon.

		WARNING: You should only call this if you want to re-calculate the vision polygon for some reason. 
		
		For normal usage, use get_vision instead!
		"""

		self.cached_radius = radius
		self.cached_position = eye
		self.debug_points = []

		radius_squared = radius * radius

		
		closest_points = lambda points, reference: sorted(points, key=lambda p: (p - reference).get_length_squared())


		def sub_segment(small, big):
			return point_on_lineseg(big[0], big[1], small[0]) and point_on_lineseg(big[0], big[1], small[1])
				
		def point_on_lineseg(a, b, p):
			crossproduct = (p.y - a.y) * (b.x - a.x) - (p.x - a.x) * (b.y - a.y)
			return abs(crossproduct) < 0.01 and min(a.x, b.x) <= p.x and p.x <= max(a.x, b.x) and min(a.y, b.y) <= p.y and p.y <= max(a.y, b.y)

		def segment_in_obs(seg):
			for line_segment in self.obs_segs:
				if sub_segment(seg, line_segment):
					return True
			return False

		def check_visibility(p):
			bpoints = set(boundary.points)
			if (eye - p).get_length_squared() > radius_squared and p not in bpoints: return False

			for line_segment in obs_segs:
				if Math.check_intersect_lineseg_lineseg( eye, p, line_segment[0], line_segment[1]): 
					if line_segment[0] != p and line_segment[1] != p:
						return False

			return True

		def lineseg_in_radius(seg):
			return distance_point_lineseg_squared(eye, seg[0], seg[1]) <= radius_squared

		obs_segs = filter(lineseg_in_radius, self.obs_segs)

		# add all obstruction points and boundary points directly visible from the eye
		visible_points = list(filter(check_visibility, set(self.obs_points + boundary.points )))

		# find all obstructors intersecting the vision polygon
		boundary_intersection_points = Math.intersect_linesegs_linesegs(obs_segs, zip(boundary.points, boundary.points[1:]) + [(boundary.points[-1], boundary.points[0])])
		
		if self.debug: self.debug_points += [(p, 0xFF0000) for p in visible_points]
		if self.debug: self.debug_points += [(p, 0x00FFFF) for p in boundary_intersection_points]

		# filter boundary_intersection_points to only include visible points 
		# - need extra code here to handle points on obstructors!
		for line_segment in obs_segs:		
			i = 0
			while i < len(boundary_intersection_points):
				p = boundary_intersection_points[i]
				vis = True
				
				if not point_on_lineseg(line_segment[0], line_segment[1], p) and Math.check_intersect_lineseg_lineseg(eye, p, line_segment[0], line_segment[1]):
					boundary_intersection_points.remove(p)
				else:
					i+=1

		visible_points += boundary_intersection_points

		poly = Math.Polygon()
		poly.add_points(visible_points)
		poly.sort_around(eye)

		i = 0
		while i < len(poly.points):
			p = poly.points[i-1]
			c = poly.points[i]
			n = poly.points[ (i+1) % len(poly.points) ]

			# intersect visible point with obstructors and boundary polygon
			intersections = Math.intersect_linesegs_ray(obs_segs, eye, c) + Math.intersect_poly_ray(boundary.points, eye, c)

			if intersections:
				# find closest intersection point and add it to point list
				closest_intersection = closest_points(intersections, eye)[0]

				if self.debug: print "%d prev: %s current: %s next: %s" % (i, p, c, n)

				if (eye - closest_intersection).get_length_squared() > radius_squared:
					closest_intersection = (closest_intersection - eye).normalize() * radius + eye

				sio_pc = segment_in_obs((p,c))
				sio_cn = segment_in_obs((c,n))

				if not sio_pc:
					if self.debug: print "insert %s at %d" % (closest_intersection, i)
					poly.points.insert(i, closest_intersection)
					i+=1


					# We might have wrongly inserted a point before because this insert was missing
					# and therefore the current-next check (incorrectly) yielded false. remove the point again
					if segment_in_obs((poly.points[i-3], poly.points[i-1])):
						if self.debug: print "Fixing erroneous insert at %d" % (i-2)
						poly.points.remove(poly.points[i-2])
						i-=1

				elif sio_pc and not sio_cn:
					
					if self.debug: print "insert %s at %d (+)" % (closest_intersection, i+1)
					poly.points.insert(i+1, closest_intersection)
					i+=1

				elif self.debug:
					print "no insert at %i" % i


			i+=1

			if self.debug: print "%d %d" % (i, len(poly.points))


		# handle border case where polypoint at 0 is wrongfully inserted before because poly was not finished at -1
		if segment_in_obs((poly.points[-1], poly.points[1])):
			poly.points[0], poly.points[1] = poly.points[1], poly.points[0]


		self.cached_vision = poly

		return poly


