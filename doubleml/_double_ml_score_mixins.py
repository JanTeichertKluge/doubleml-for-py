import numpy as np

import warnings

from scipy.optimize import fmin_l_bfgs_b, root_scalar

from abc import abstractmethod


class LinearScoreMixin:
    _score_type = 'linear'

    @property
    def _score_element_names(self):
        return ['psi_a', 'psi_b']

    def _compute_score(self, psi_elements, coef, inds=None):
        psi_a = psi_elements['psi_a']
        psi_b = psi_elements['psi_b']
        if inds is not None:
            psi_a = psi_a[inds]
            psi_b = psi_b[inds]
        psi = psi_a * coef + psi_b
        return psi

    def _compute_score_deriv(self, psi_elements, coef, inds=None):
        psi_a = psi_elements['psi_a']
        if inds is not None:
            psi_a = psi_a[inds]
        return psi_a

    def _est_coef(self, psi_elements, inds=None):
        psi_a = psi_elements['psi_a']
        psi_b = psi_elements['psi_b']
        if inds is not None:
            psi_a = psi_a[inds]
            psi_b = psi_b[inds]

        coef = -np.mean(psi_b) / np.mean(psi_a)

        return coef

    def _est_coef_cluster_data(self, psi_elements, dml_procedure, smpls, smpls_cluster):
        psi_a = psi_elements['psi_a']
        psi_b = psi_elements['psi_b']
        dml1_coefs = None

        if dml_procedure == 'dml1':
            # note that in the dml1 case we could also simply apply the standard function without cluster adjustment
            dml1_coefs = np.zeros(len(smpls))
            for i_fold, (_, test_index) in enumerate(smpls):
                test_cluster_inds = smpls_cluster[i_fold][1]
                scaling_factor = 1./np.prod(np.array([len(inds) for inds in test_cluster_inds]))
                dml1_coefs[i_fold] = - (scaling_factor * np.sum(psi_b[test_index])) / \
                    (scaling_factor * np.sum(psi_a[test_index]))
            coef = np.mean(dml1_coefs)
        else:
            assert dml_procedure == 'dml2'
            # See Chiang et al. (2021) Algorithm 1
            psi_a_subsample_mean = 0.
            psi_b_subsample_mean = 0.
            for i_fold, (_, test_index) in enumerate(smpls):
                test_cluster_inds = smpls_cluster[i_fold][1]
                scaling_factor = 1./np.prod(np.array([len(inds) for inds in test_cluster_inds]))
                psi_a_subsample_mean += scaling_factor * np.sum(psi_a[test_index])
                psi_b_subsample_mean += scaling_factor * np.sum(psi_b[test_index])
            coef = -psi_b_subsample_mean / psi_a_subsample_mean

        return coef, dml1_coefs


class NonLinearScoreMixin:
    _score_type = 'nonlinear'
    _coef_start_val = np.nan
    _coef_bounds = None

    @property
    @abstractmethod
    def _score_element_names(self):
        pass

    @abstractmethod
    def _compute_score(self, psi_elements, coef, inds=None):
        pass

    @abstractmethod
    def _compute_score_deriv(self, psi_elements, coef, inds=None):
        pass

    def _est_coef(self, psi_elements, inds=None):
        def score(theta, ii):
            res = np.mean(self._compute_score(psi_elements, theta, ii))
            return res

        def score_deriv(theta, ii):
            res = np.mean(self._compute_score_deriv(psi_elements, theta, ii))
            return res

        if self._coef_bounds is None:
            bounded = False
        else:
            bounded = (self._coef_bounds[0] > -np.inf) & (self._coef_bounds[1] < np.inf)

        if not bounded:
            root_res = root_scalar(score, (inds,),
                                   x0=self._coef_start_val,
                                   fprime=score_deriv,
                                   method='newton')
            theta_hat = root_res.root
        else:
            def get_bracket_guess(coef_start, coef_bounds):
                max_bracket_length = coef_bounds[1] - coef_bounds[0]
                b_guess = coef_bounds
                delta = 0.1
                s_different = False
                while (not s_different) & (delta <= 1.0):
                    a = np.maximum(coef_start - delta * max_bracket_length/2, coef_bounds[0])
                    b = np.minimum(coef_start + delta * max_bracket_length/2, coef_bounds[1])
                    b_guess = (a, b)
                    f_a = score(b_guess[0], inds)
                    f_b = score(b_guess[1], inds)
                    s_different = (np.sign(f_a) != np.sign(f_b))
                    delta += 0.1
                return s_different, b_guess

            signs_different, bracket_guess = get_bracket_guess(self._coef_start_val, self._coef_bounds)

            if signs_different:
                root_res = root_scalar(score, (inds,),
                                       bracket=bracket_guess,
                                       method='brentq')
                theta_hat = root_res.root
            else:
                # try to find an alternative start value
                def score_squared(theta, ii):
                    res = np.power(np.mean(self._compute_score(psi_elements, theta, ii)), 2)
                    return res
                # def score_squared_deriv(theta, inds):
                #     res = 2 * np.mean(self._compute_score(psi_elements, theta, inds)) * \
                #           np.mean(self._compute_score_deriv(psi_elements, theta, inds))
                #     return res
                alt_coef_start, _, _ = fmin_l_bfgs_b(score_squared,
                                                     self._coef_start_val,
                                                     args=(inds, ),
                                                     approx_grad=True,
                                                     bounds=[self._coef_bounds])
                signs_different, bracket_guess = get_bracket_guess(alt_coef_start, self._coef_bounds)

                if signs_different:
                    root_res = root_scalar(score, (inds,),
                                           bracket=bracket_guess,
                                           method='brentq')
                    theta_hat = root_res.root
                else:
                    score_val_sign = np.sign(score(alt_coef_start, inds))
                    if score_val_sign > 0:
                        theta_hat, score_val, _ = fmin_l_bfgs_b(score,
                                                                self._coef_start_val,
                                                                args=(inds, ),
                                                                approx_grad=True,
                                                                bounds=[self._coef_bounds])
                        warnings.warn('Could not find a root of the score function.\n '
                                      f'Minimum score value found is {score_val} '
                                      f'for parameter theta equal to {theta_hat}.\n '
                                      'No theta found such that the score function evaluates to a negative value.')
                    else:
                        def neg_score(theta, ii):
                            res = np.mean(self._compute_score(psi_elements, theta, ii))
                            return res
                        theta_hat, neg_score_val, _ = fmin_l_bfgs_b(neg_score,
                                                                    self._coef_start_val,
                                                                    args=(inds, ),
                                                                    approx_grad=True,
                                                                    bounds=[self._coef_bounds])
                        warnings.warn('Could not find a root of the score function. '
                                      f'Maximum score value found is {-1*neg_score_val} '
                                      f'for parameter theta equal to {theta_hat}. '
                                      'No theta found such that the score function evaluates to a positive value.')

        return theta_hat
