
"""
Copyright 2017 Steven Diamond

This file is part of CVXPY.

CVXPY is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CVXPY is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CVXPY.  If not, see <http://www.gnu.org/licenses/>.
"""

from cvxpy.reductions import Reduction, Solution
from cvxpy.atoms import reshape
from cvxpy.expressions.constants import Constant
from cvxpy.expressions.variable import Variable, upper_tri_to_full
import numpy as np


class CvxAttr2Constr(Reduction):
    """Expand convex variable attributes into constraints."""

    def accepts(self, problem):
        return True

    def apply(self, problem):
        # For each unique variable, add constraints.
        id2new_var = {}
        id2new_obj = {}
        id2old_var = {}
        constr = []
        for var in problem.variables():
            if var.id not in id2new_var:
                id2old_var[var.id] = var
                new_var = False
                new_attr = var.attributes.copy()
                for key in ['nonneg', 'nonpos', 'symmetric', 'PSD', 'NSD']:
                    if new_attr[key]:
                        new_var = True
                        new_attr[key] = False

                if var.is_symmetric():
                    n = var.shape[0]
                    shape = (n*(n+1)//2, 1)
                    upper_tri = Variable(shape, **new_attr)
                    id2new_var[var.id] = upper_tri
                    fill_coeff = Constant(upper_tri_to_full(n))
                    full_mat = fill_coeff*upper_tri
                    obj = reshape(full_mat, (n, n))
                elif new_var:
                    obj = Variable(var.shape, **new_attr)
                    id2new_var[var.id] = obj
                else:
                    obj = var
                    id2new_var[var.id] = obj

                id2new_obj[var.id] = obj
                constr = []
                if var.is_nonneg():
                    constr.append(obj >= 0)
                elif var.is_nonpos():
                    constr.append(obj <= 0)
                elif var.attributes['PSD']:
                    constr.append(obj >> 0)
                elif var.attributes['NSD']:
                    constr.append(obj << 0)

        inverse_data = (id2new_var, id2old_var)
        new_problem = problem.tree_copy(id_objects=id2new_obj)
        return new_problem, inverse_data

    def invert(self, solution, inverse_data):
        id2new_var, id2old_var = inverse_data
        pvars = {}
        for id, var in id2old_var:
            new_var = id2new_var[id]
            # Need to map from constrained to symmetric variable.
            if new_var.id in solution.primal_vars:
                if var.is_symmetric():
                    n = var.shape[0]
                    value = np.zeros(var.shape)
                    value[:n*(n+1)//2] = solution.primal_vars[new_var.id]
                    pvars[id] = value + value.T
                else:
                    pvars[id] = solution.primal_vars[new_var.id]
        return Solution(solution.status, solution.opt_val, pvars, solution.dual_vars)
