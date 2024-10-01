from copy import deepcopy
from itertools import cycle

import experiments.fitting as fitter
import matplotlib.pyplot as plt
import numpy as np
from experiments.clifford_averager_program import (
    QutritAveragerProgram,
    ps_threshold_adjust,
)
from qick import *
from qick.helpers import gauss
from slab import AttrDict, Experiment, dsfit
from tqdm import tqdm_notebook as tqdm

default_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
linestyle_cycle = ["solid", "dashed", "dotted", "dashdot"]
marker_cycle = ["o", "*", "s", "^"]

# Use np.hist and plt.plot to accomplish plt.hist with less memory usage
def plot_hist(
    data,
    bins,
    ax=None,
    xlims=None,
    color=None,
    linestyle=None,
    label=None,
    alpha=None,
    normalize=True,
):
    if color is None:
        color_cycle = cycle(default_colors)
        color = next(color_cycle)
    hist_data, bin_edges = np.histogram(data, bins=bins, range=xlims)
    if normalize:
        hist_data = hist_data / hist_data.sum()
    for i in range(len(hist_data)):
        if i > 0:
            label = None
        ax.plot(
            [bin_edges[i], bin_edges[i + 1]],
            [hist_data[i], hist_data[i]],
            color=color,
            linestyle=linestyle,
            label=label,
            alpha=alpha,
            linewidth=0.9,
        )
        if i < len(hist_data) - 1:
            ax.plot(
                [bin_edges[i + 1], bin_edges[i + 1]],
                [hist_data[i], hist_data[i + 1]],
                color=color,
                linestyle=linestyle,
                alpha=alpha,
                linewidth=0.9,
            )
    ax.relim()
    ax.set_ylim((0, None))
    return hist_data, bin_edges


def hist(data, plot=True, span=None, verbose=True, title=None, fid_avg=False):
    """
    span: histogram limit is the mean +/- span
    fid_avg: if True, calculate fidelity F by the average mis-categorized e/g; otherwise count
        total number of miscategorized over total counts (gives F^2)
    """
    Ig = data["Ig"]
    Qg = data["Qg"]
    Ie = data["Ie"]
    Qe = data["Qe"]
    plot_f = False
    if "If" in data.keys():
        plot_f = True
        If = data["If"]
        Qf = data["Qf"]

    numbins = 200

    xg, yg = np.average(Ig), np.average(Qg)
    xe, ye = np.average(Ie), np.average(Qe)
    if plot_f:
        xf, yf = np.average(If), np.average(Qf)

    if verbose:
        print("Unrotated:")
        print(
            f"Ig {xg} +/- {np.std(Ig)} \t Qg {yg} +/- {np.std(Qg)} \t Amp g {np.abs(xg+1j*yg)} +/- {np.std(np.abs(Ig + 1j*Qg))}"
        )
        print(
            f"Ie {xe} +/- {np.std(Ie)} \t Qe {ye} +/- {np.std(Qe)} \t Amp e {np.abs(xe+1j*ye)} +/- {np.std(np.abs(Ig + 1j*Qe))}"
        )
        if plot_f:
            print(f"If {xf} +/- {np.std(If)} \t Qf {yf} +/- {np.std(Qf)} \t Amp f {np.abs(xf+1j*yf)}")

    if plot:
        fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(9, 6))
        if title is not None:
            plt.suptitle(title)
        fig.tight_layout()

        axs[0, 0].scatter(Ig, Qg, label="g", color="b", marker=".", edgecolor="None", alpha=0.2)
        axs[0, 0].scatter(Ie, Qe, label="e", color="r", marker=".", edgecolor="None", alpha=0.2)
        if plot_f:
            axs[0, 0].scatter(If, Qf, label="f", color="g", marker=".", edgecolor="None", alpha=0.2)
        axs[0, 0].plot(
            [xg],
            [yg],
            color="k",
            linestyle=":",
            marker="o",
            markerfacecolor="b",
            markersize=5,
        )
        axs[0, 0].plot(
            [xe],
            [ye],
            color="k",
            linestyle=":",
            marker="o",
            markerfacecolor="r",
            markersize=5,
        )
        if plot_f:
            axs[0, 0].plot(
                [xf],
                [yf],
                color="k",
                linestyle=":",
                marker="o",
                markerfacecolor="g",
                markersize=5,
            )

        # axs[0,0].set_xlabel('I [ADC levels]')
        axs[0, 0].set_ylabel("Q [ADC levels]", fontsize=12)
        axs[0, 0].tick_params(axis="both", which="major", labelsize=10)
        axs[0, 0].legend(loc="upper right")
        axs[0, 0].set_title("Unrotated", fontsize=12)
        axs[0, 0].axis("equal")

    """Compute the rotation angle"""
    theta = -np.arctan2((ye - yg), (xe - xg))
    if plot_f:
        theta = -np.arctan2((yf - yg), (xf - xg))

    """Rotate the IQ data"""
    Ig_new = Ig * np.cos(theta) - Qg * np.sin(theta)
    Qg_new = Ig * np.sin(theta) + Qg * np.cos(theta)

    Ie_new = Ie * np.cos(theta) - Qe * np.sin(theta)
    Qe_new = Ie * np.sin(theta) + Qe * np.cos(theta)

    if plot_f:
        If_new = If * np.cos(theta) - Qf * np.sin(theta)
        Qf_new = If * np.sin(theta) + Qf * np.cos(theta)

    """New means of each blob"""
    xg, yg = np.average(Ig_new), np.average(Qg_new)
    xe, ye = np.average(Ie_new), np.average(Qe_new)
    if plot_f:
        xf, yf = np.average(If_new), np.average(Qf_new)
    if verbose:
        print("Rotated:")
        print(
            f"Ig {xg} +/- {np.std(Ig)} \t Qg {yg} +/- {np.std(Qg)} \t Amp g {np.abs(xg+1j*yg)} +/- {np.std(np.abs(Ig + 1j*Qg))}"
        )
        print(
            f"Ie {xe} +/- {np.std(Ie)} \t Qe {ye} +/- {np.std(Qe)} \t Amp e {np.abs(xe+1j*ye)} +/- {np.std(np.abs(Ig + 1j*Qe))}"
        )
        if plot_f:
            print(f"If {xf} +/- {np.std(If)} \t Qf {yf} +/- {np.std(Qf)} \t Amp f {np.abs(xf+1j*yf)}")

    span = (np.max(np.concatenate((Ie_new, Ig_new))) - np.min(np.concatenate((Ie_new, Ig_new)))) / 2
    lim_midpoint = (np.max(np.concatenate((Ie_new, Ig_new))) + np.min(np.concatenate((Ie_new, Ig_new)))) / 2
    if plot_f:
        span = (
            np.max(np.concatenate((If_new, Ie_new, Ig_new))) - np.min(np.concatenate((If_new, Ie_new, Ig_new)))
        ) / 2
        lim_midpoint = (
            np.max(np.concatenate((If_new, Ie_new, Ig_new))) + np.min(np.concatenate((If_new, Ie_new, Ig_new)))
        ) / 2
    xlims = [lim_midpoint - span, lim_midpoint + span]

    if plot:
        axs[0, 1].scatter(
            Ig_new,
            Qg_new,
            label="g",
            color="b",
            marker=".",
            edgecolor="None",
            alpha=0.3,
        )
        axs[0, 1].scatter(
            Ie_new,
            Qe_new,
            label="e",
            color="r",
            marker=".",
            edgecolor="None",
            alpha=0.3,
        )
        if plot_f:
            axs[0, 1].scatter(
                If_new,
                Qf_new,
                label="f",
                color="g",
                marker=".",
                edgecolor="None",
                alpha=0.3,
            )
        axs[0, 1].plot(
            [xg],
            [yg],
            color="k",
            linestyle=":",
            marker="o",
            markerfacecolor="b",
            markersize=5,
        )
        axs[0, 1].plot(
            [xe],
            [ye],
            color="k",
            linestyle=":",
            marker="o",
            markerfacecolor="r",
            markersize=5,
        )
        if plot_f:
            axs[0, 1].plot(
                [xf],
                [yf],
                color="k",
                linestyle=":",
                marker="o",
                markerfacecolor="g",
                markersize=5,
            )

        # axs[0,1].set_xlabel('I [ADC levels]')
        axs[0, 1].legend(loc="upper right")
        axs[0, 1].set_title("Rotated", fontsize=12)
        axs[0, 1].axis("equal")
        axs[0, 1].tick_params(axis="both", which="major", labelsize=10)

        """X and Y ranges for histogram"""

        ng, binsg, pg = axs[1, 0].hist(Ig_new, bins=numbins, range=xlims, color="b", label="g", alpha=0.5)
        ne, binse, pe = axs[1, 0].hist(Ie_new, bins=numbins, range=xlims, color="r", label="e", alpha=0.5)
        if plot_f:
            nf, binsf, pf = axs[1, 0].hist(If_new, bins=numbins, range=xlims, color="g", label="f", alpha=0.5)
        axs[1, 0].set_ylabel("Counts", fontsize=12)
        axs[1, 0].set_xlabel("I [ADC levels]", fontsize=12)
        axs[1, 0].legend(loc="upper right")
        axs[1, 0].tick_params(axis="both", which="major", labelsize=10)

    else:
        ng, binsg = np.histogram(Ig_new, bins=numbins, range=xlims)
        ne, binse = np.histogram(Ie_new, bins=numbins, range=xlims)
        if plot_f:
            nf, binsf = np.histogram(If_new, bins=numbins, range=xlims)

    """Compute the fidelity using overlap of the histograms"""
    fids = []
    thresholds = []
    contrast = np.abs(
        ((np.cumsum(ng) - np.cumsum(ne)) / (0.5 * ng.sum() + 0.5 * ne.sum()))
    )  # this method calculates fidelity as 1-2(Neg + Nge)/N
    tind = contrast.argmax()
    thresholds.append(binsg[tind])
    if not fid_avg:
        fids.append(contrast[tind])
    else:
        fids.append(
            0.5 * (1 - ng[tind:].sum() / ng.sum() + 1 - ne[:tind].sum() / ne.sum())
        )  # this method calculates fidelity as (Ngg+Nee)/N = Ngg/N + Nee/N=(0.5N-Nge)/N + (0.5N-Neg)/N = 1-(Nge+Neg)/N
    if verbose:
        print(f"g correctly categorized: {100*(1-ng[tind:].sum()/ng.sum())}%")
        print(f"e correctly categorized: {100*(1-ne[:tind].sum()/ne.sum())}%")
    if plot_f:
        contrast = np.abs(((np.cumsum(ng) - np.cumsum(nf)) / (0.5 * ng.sum() + 0.5 * nf.sum())))
        tind = contrast.argmax()
        thresholds.append(binsg[tind])
        if not fid_avg:
            fids.append(contrast[tind])
        else:
            fids.append(0.5 * (1 - ng[tind:].sum() / ng.sum() + 1 - nf[:tind].sum() / nf.sum()))

        contrast = np.abs(((np.cumsum(ne) - np.cumsum(nf)) / (0.5 * ne.sum() + 0.5 * nf.sum())))
        tind = contrast.argmax()
        thresholds.append(binsg[tind])
        if not fid_avg:
            fids.append(contrast[tind])
        else:
            fids.append(0.5 * (1 - ne[tind:].sum() / ne.sum() + 1 - nf[:tind].sum() / nf.sum()))

    if plot:
        title = "$\overline{F}_{ge}$" if fid_avg else "$F_{ge}$"
        axs[1, 0].set_title(f"Histogram ({title}: {100*fids[0]:.3}%)", fontsize=14)
        axs[1, 0].axvline(thresholds[0], color="0.2", linestyle="--")
        if plot_f:
            axs[1, 0].axvline(thresholds[1], color="0.2", linestyle="--")
            axs[1, 0].axvline(thresholds[2], color="0.2", linestyle="--")

        axs[1, 1].set_title("Cumulative Counts", fontsize=14)
        axs[1, 1].plot(binsg[:-1], np.cumsum(ng), "b", label="g")
        axs[1, 1].plot(binse[:-1], np.cumsum(ne), "r", label="e")
        axs[1, 1].axvline(thresholds[0], color="0.2", linestyle="--")
        if plot_f:
            axs[1, 1].plot(binsf[:-1], np.cumsum(nf), "g", label="f")
            axs[1, 1].axvline(thresholds[1], color="0.2", linestyle="--")
            axs[1, 1].axvline(thresholds[2], color="0.2", linestyle="--")
        axs[1, 1].legend()
        axs[1, 1].set_xlabel("I [ADC levels]", fontsize=12)
        axs[1, 1].tick_params(axis="both", which="major", labelsize=10)

        plt.subplots_adjust(hspace=0.25, wspace=0.15)
        plt.show()

    return fids, thresholds, theta * 180 / np.pi  # fids: ge, gf, ef


# ===================================================================== #


def multihist(
    data,
    check_qubit,
    check_states,
    play_pulses_list,
    g_states,
    e_states,
    qubits=None,
    numbins=200,
    ps_threshold=None,
    theta=None,
    plot=True,
    verbose=True,
    fit=False,
    fitparams=None,
    normalize=True,
    title=None,
    export=False,
    check_qnd=False,
):
    """
    span: histogram limit is the mean +/- span
    theta given and returned in deg
    assume data is passed in form data['iqshots'] = [(idata, qdata)]*len(check_states), idata=[... *num_shots]*num_qubits_sample
    check_states: an array of strs of the init_state specifying each configuration to plot a histogram for
    play_pulses_list: list of play_pulses corresponding to check_states, see code for play_pulses
    g_states are indices to the check_states to categorize as "g" (the rest are "e")
    normalize: normalizes counts by total counts
    """
    if numbins is None:
        numbins = 200
    iqshots = data["iqshots"]
    assert len(play_pulses_list) == len(check_states)

    # total histograms for shots listed as g or e
    Ig_tot = []
    Qg_tot = []
    Ie_tot = []
    Qe_tot = []

    # the actual total histograms of everything
    Ig_tot_tot = []
    Qg_tot_tot = []
    Ie_tot_tot = []
    Qe_tot_tot = []
    for check_i, data_check in enumerate(iqshots):
        I, Q = data_check
        I = I[check_qubit]
        Q = Q[check_qubit]
        Ig_tot_tot = np.concatenate((Ig_tot_tot, I))
        Qg_tot_tot = np.concatenate((Qg_tot_tot, Q))
        Ie_tot_tot = np.concatenate((Ig_tot_tot, I))
        Qe_tot_tot = np.concatenate((Qg_tot_tot, Q))
        if check_i in g_states:
            Ig_tot = np.concatenate((Ig_tot, I))
            Qg_tot = np.concatenate((Qg_tot, Q))
        elif check_i in e_states:
            Ie_tot = np.concatenate((Ig_tot, I))
            Qe_tot = np.concatenate((Qg_tot, Q))

    """Compute the rotation angle"""
    if theta is None:
        xg, yg = np.average(Ig_tot), np.average(Qg_tot)
        xe, ye = np.average(Ie_tot), np.average(Qe_tot)
        theta = -np.arctan2((ye - yg), (xe - xg))
    else:
        theta *= np.pi / 180

    Ig_tot_tot_new = Ig_tot_tot * np.cos(theta) - Qg_tot_tot * np.sin(theta)
    Qg_tot_tot_new = Ig_tot_tot * np.sin(theta) + Qg_tot_tot * np.cos(theta)
    Ie_tot_tot_new = Ie_tot_tot * np.cos(theta) - Qe_tot_tot * np.sin(theta)
    Qe_tot_tot_new = Ie_tot_tot * np.sin(theta) + Qe_tot_tot * np.cos(theta)
    I_tot_tot_new = np.concatenate((Ie_tot_tot_new, Ig_tot_tot_new))
    span = (np.max(I_tot_tot_new) - np.min(I_tot_tot_new)) / 2
    midpoint = (np.max(I_tot_tot_new) + np.min(I_tot_tot_new)) / 2
    xlims = [midpoint - span, midpoint + span]
    y_max = 0

    n_tot_g = [0] * numbins
    n_tot_e = [0] * numbins
    if fit:
        popts = [None] * len(check_states)
        pcovs = [None] * len(check_states)

    if plot:
        fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(9, 6))
        if title is None:
            title = f"Readout on $|Q{qubits[0]}\\rangle |Q{qubits[1]}\\rangle$, check Q{check_qubit}"
        fig.suptitle(title)
        fig.tight_layout()
        axs[0, 0].set_ylabel("Q [ADC levels]", fontsize=12)
        axs[0, 0].set_title("Unrotated", fontsize=12)
        axs[0, 0].axis("equal")
        axs[0, 0].tick_params(axis="both", which="major", labelsize=10)

        axs[0, 1].axis("equal")

        plt.subplots_adjust(hspace=0.25, wspace=0.15)

    for check_i, data_check in enumerate(iqshots):
        check_state = check_states[check_i]
        play_pulses = play_pulses_list[check_i]

        I, Q = data_check
        I = I[check_qubit]
        Q = Q[check_qubit]

        xavg, yavg = np.average(I), np.average(Q)

        if verbose:
            print(check_state, "play_pulses", play_pulses, "unrotated averages:")
            print(f"I {xavg} +/- {np.std(I)} \t Q {yavg} +/- {np.std(Q)} \t Amp {np.abs(xavg+1j*yavg)}")

        """Rotate the IQ data"""
        I_new = I * np.cos(theta) - Q * np.sin(theta)
        Q_new = I * np.sin(theta) + Q * np.cos(theta)

        """New means of each blob"""
        xavg_new, yavg_new = np.average(I_new), np.average(Q_new)
        if verbose:
            print(f"Rotated (theta={theta}):")
            print(
                f"I {xavg_new} +/- {np.std(I_new)} \t Q {yavg_new} +/- {np.std(Q_new)} \t Amp {np.abs(xavg_new+1j*yavg_new)}"
            )

        if plot:
            label = f"{check_state}"
            # print('check state', check_state)
            if len(play_pulses) > 1 or play_pulses[0] != 0:
                label += f" play {play_pulses}"
            axs[0, 0].scatter(
                I,
                Q,
                label=label,
                color=default_colors[check_i % len(default_colors)],
                marker=".",
                edgecolor="None",
                alpha=0.3,
            )
            axs[0, 0].plot(
                [xavg],
                [yavg],
                color="k",
                linestyle=":",
                marker="o",
                markerfacecolor=default_colors[check_i % len(default_colors)],
                markersize=5,
            )

            axs[0, 1].scatter(
                I_new,
                Q_new,
                label=label,
                color=default_colors[check_i % len(default_colors)],
                marker=".",
                edgecolor="None",
                alpha=0.3,
            )
            axs[0, 1].plot(
                [xavg_new],
                [yavg_new],
                color="k",
                linestyle=":",
                marker="o",
                markerfacecolor=default_colors[check_i % len(default_colors)],
                markersize=5,
            )

            if check_i in g_states or check_i in e_states:
                linestyle = linestyle_cycle[0]
            else:
                linestyle = linestyle_cycle[1]

            # n, bins, p = axs[1,0].hist(I_new, bins=numbins, range=xlims, color=default_colors[check_i % len(default_colors)], label=label, histtype='step', linestyle=linestyle)
            n, bins = plot_hist(
                I_new,
                bins=numbins,
                ax=axs[1, 0],
                xlims=xlims,
                color=default_colors[check_i % len(default_colors)],
                label=label,
                linestyle=linestyle,
                normalize=normalize,
            )
            # n, bins = np.histogram(I_new, bins=numbins, range=xlims)
            # axs[1,0].plot(bins[:-1], n/n.sum(), color=default_colors[check_i % len(default_colors)], linestyle=linestyle)

            axs[1, 1].plot(
                bins[:-1],
                np.cumsum(n) / n.sum(),
                color=default_colors[check_i % len(default_colors)],
                linestyle=linestyle,
            )

        else:  # just getting the n, bins for data processing
            n, bins = np.histogram(I_new, bins=numbins, range=xlims)

        if check_i in g_states:
            n_tot_g += n
            bins_g = bins
        elif check_i in e_states:
            n_tot_e += n
            bins_e = bins

        if check_qnd:
            if check_state == "g_0":
                n_g_0 = n
            if check_state == "g_1":
                n_g_1 = n

    if check_qnd:
        n_diff = np.abs((n_g_0 - n_g_1))
        data["n_diff_qnd"] = np.sum(n_diff) / 2 / np.sum(n_g_0)

    if fit:
        # a bit stupid but we need to know what the g and e states are to fit the gaussians
        for check_i, data_check in enumerate(iqshots):
            check_state = check_states[check_i]
            play_pulses = play_pulses_list[check_i]

            I, Q = data_check
            I = I[check_qubit]
            Q = Q[check_qubit]

            xavg, yavg = np.average(I), np.average(Q)

            if verbose:
                print(check_state, "play_pulses", play_pulses, "unrotated averages:")
                print(f"I {xavg} +/- {np.std(I)} \t Q {yavg} +/- {np.std(Q)} \t Amp {np.abs(xavg+1j*yavg)}")

            """Rotate the IQ data"""
            I_new = I * np.cos(theta) - Q * np.sin(theta)
            Q_new = I * np.sin(theta) + Q * np.cos(theta)

            n, bins = np.histogram(I_new, bins=numbins, range=xlims)

            xmax_g = bins_g[np.argmax(n_tot_g)]
            xmax_e = bins_e[np.argmax(n_tot_e)]
            idx_g = np.argmin(np.abs(bins[:-1] - xmax_g))
            idx_e = np.argmin(np.abs(bins[:-1] - xmax_e))
            ymax_g = n[idx_g]
            ymax_e = n[idx_e]
            fitparams = [ymax_g, xmax_g, 100, ymax_e, xmax_e, 100]

            popt, pcov = fitter.fit_doublegauss(xdata=bins[:-1], ydata=n, fitparams=fitparams)

            if plot:
                y = fitter.double_gaussian(bins[:-1], *popt)
                y_norm = y / y.sum()

                axs[1, 0].plot(
                    bins[:-1],
                    y_norm,
                    "-",
                    color=default_colors[check_i % len(default_colors)],
                )
                if y_norm.max() > y_max:
                    y_max = y_norm.max()
                    print(y_max)
                    print(y_norm.max())

                axs[1, 0].set_ylim((0, y_max * 1.1))

            popts[check_i] = popt
            pcovs[check_i] = pcov

    """Compute the fidelity using overlap of the histograms"""
    fids = []
    thresholds = []
    contrast = np.abs(np.cumsum(n_tot_g) / n_tot_g.sum() - np.cumsum(n_tot_e) / n_tot_e.sum())
    tind = contrast.argmax()
    thresholds.append(bins[tind])
    # thresholds.append(np.average([bins_e[idx_e], bins_g[idx_g]]))
    fids.append(contrast[tind])

    if plot:
        axs[0, 1].set_title(f"Rotated ($\\theta={theta*180/np.pi:.5}^\\circ$)", fontsize=12)
        axs[0, 1].tick_params(axis="both", which="major", labelsize=10)

        axs[1, 0].axvline(thresholds[0], color="0.2", linestyle="--")
        axs[1, 0].set_title(f"Fidelity g-e: {100*fids[0]:.3}%", fontsize=12)
        axs[1, 0].set_ylabel("Counts", fontsize=12)
        axs[1, 0].set_xlabel("I [ADC levels]", fontsize=12)
        axs[1, 0].tick_params(axis="both", which="major", labelsize=10)
        if ps_threshold is not None:
            axs[1, 0].axvline(ps_threshold, color="0.2", linestyle="-.")

        axs[1, 1].set_title("Cumulative Sum", fontsize=12)
        axs[1, 1].plot(bins[:-1], np.cumsum(n_tot_g) / n_tot_g.sum(), "b", label="g")
        axs[1, 1].plot(bins[:-1], np.cumsum(n_tot_e) / n_tot_e.sum(), "r", label="e")
        axs[1, 1].axvline(thresholds[0], color="0.2", linestyle="--")
        axs[1, 1].set_xlabel("I [ADC levels]", fontsize=12)
        axs[1, 1].tick_params(axis="both", which="major", labelsize=10)

        prop = {"size": 8}
        axs[0, 0].legend(loc="upper right", prop=prop)
        axs[0, 1].legend(loc="upper right", prop=prop)
        axs[1, 0].legend(loc="upper left", prop=prop)
        axs[1, 1].legend(prop=prop)

        if export:
            plt.savefig("multihist.jpg", dpi=1000)
            print("exported multihist.jpg")
            plt.close()
        else:
            print("wheres my plot")
            plt.show()

    if not fit:
        return fids, thresholds, theta * 180 / np.pi  # fids: ge, gf, ef
    return fids, thresholds, theta * 180 / np.pi, popts, pcovs


# ------------------------------------------------------- #

# ====================================================== #


class HistogramProgram(QutritAveragerProgram):
    def body(self):
        cfg = AttrDict(self.cfg)

        qTest = self.cfg.expt.qTest
        qZZ = None
        self.checkZZ = False
        if "qZZ" in self.cfg.expt and self.cfg.expt.qZZ is not None:
            qZZ = self.cfg.expt.qZZ
            self.checkZZ = True
        if qZZ is None:
            qZZ = qTest

        self.reset_and_sync()

        if "cool_qubits" in self.cfg.expt and self.cfg.expt.cool_qubits is not None:
            cool_idle = [self.cfg.device.qubit.pulses.pi_f0g1.idle[q] for q in self.cfg.expt.cool_qubits]
            if "cool_idle" in self.cfg.expt and self.cfg.expt.cool_idle is not None:
                cool_idle = self.cfg.expt.cool_idle
            self.active_cool(cool_qubits=self.cfg.expt.cool_qubits, cool_idle=cool_idle)

        # initializations as necessary
        if self.checkZZ:
            self.X_pulse(q=qZZ, play=True)

        if self.cfg.expt.pulse_e:
            self.X_pulse(q=qTest, ZZ_qubit=qZZ, play=True)

        if self.cfg.expt.pulse_f:
            self.Xef_pulse(q=qTest, ZZ_qubit=qZZ, play=True)

        self.measure(
            pulse_ch=self.measure_chs,
            adcs=self.adc_chs,
            adc_trig_offset=cfg.device.readout.trig_offset[0],
            wait=True,
            syncdelay=self.us2cycles(max([cfg.device.readout.relax_delay[q] for q in range(4)])),
        )

    def collect_shots(self, qubit=None, angle=None, threshold=None, avg_shots=False, verbose=False):
        if qubit is None:
            qubit = self.cfg.expt.qTest
        idata, qdata = self.get_shots(angle=angle, threshold=threshold, avg_shots=avg_shots, verbose=verbose)
        return idata[qubit], qdata[qubit]


class HistogramExperiment(Experiment):
    """
    Histogram Experiment
    expt = dict(
        reps: number of shots per expt
        check_e: whether to test the e state blob (true if unspecified)
        check_f: whether to also test the f state blob
    )
    """

    def __init__(self, soccfg=None, path="", prefix="Histogram", config_file=None, progress=None):
        super().__init__(
            soccfg=soccfg,
            path=path,
            prefix=prefix,
            config_file=config_file,
            progress=progress,
        )

    def acquire(self, progress=False):
        # expand entries in config that are length 1 to fill all qubits
        num_qubits_sample = len(self.cfg.device.readout.frequency)
        for subcfg in (self.cfg.device.readout, self.cfg.device.qubit, self.cfg.hw.soc):
            for key, value in subcfg.items():
                if isinstance(value, dict):
                    for key2, value2 in value.items():
                        if isinstance(value2, dict):
                            for key3, value3 in value2.items():
                                if not (isinstance(value3, list)):
                                    value2.update({key3: [value3] * num_qubits_sample})
                elif not (isinstance(value, list)):
                    subcfg.update({key: [value] * num_qubits_sample})

        data = dict()

        # Ground state shots
        cfg = AttrDict(deepcopy(self.cfg))
        cfg.expt.pulse_e = False
        cfg.expt.pulse_f = False
        cfg.expt.pulse_test = False
        histpro = HistogramProgram(soccfg=self.soccfg, cfg=cfg)
        avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
        self.prog = histpro
        data["Ig"], data["Qg"] = histpro.collect_shots()

        # Excited state shots
        if "check_e" not in self.cfg.expt:
            self.check_e = True
        else:
            self.check_e = self.cfg.expt.check_e
        if self.check_e:
            cfg = AttrDict(deepcopy(self.cfg))
            cfg.expt.pulse_e = True
            cfg.expt.pulse_f = False
            cfg.expt.pulse_test = False
            histpro = HistogramProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["Ie"], data["Qe"] = histpro.collect_shots()

        # Excited f state shots
        self.check_f = self.cfg.expt.check_f
        if self.check_f:
            cfg = AttrDict(deepcopy(self.cfg))
            cfg.expt.pulse_e = True
            # cfg.expt.pulse_e = False
            # print('WARNING TURNED OFF PULSE E FOR CHECK F')
            cfg.expt.pulse_f = True
            cfg.expt.pulse_test = False
            histpro = HistogramProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["If"], data["Qf"] = histpro.collect_shots()

        # Test state shots
        if "pulse_test" not in self.cfg.expt:
            self.cfg.expt.pulse_test = False
        self.check_test = self.cfg.expt.pulse_test
        if self.check_test:
            cfg = AttrDict(deepcopy(self.cfg))
            histpro = HistogramProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["Itest"], data["Qtest"] = histpro.collect_shots()

        self.data = data
        return data

    def analyze(self, data=None, span=None, verbose=True, **kwargs):
        if data is None:
            data = self.data

        fids, thresholds, angle = hist(data=data, plot=False, span=span, verbose=verbose)
        data["fids"] = fids
        data["angle"] = angle
        data["thresholds"] = thresholds

        return data

    def display(self, data=None, span=None, verbose=True, **kwargs):
        if data is None:
            data = self.data

        qTest = self.cfg.expt.qTest
        fids, thresholds, angle = hist(data=data, plot=True, verbose=verbose, span=span, title=f"Qubit {qTest}")

        print(f"ge fidelity (%): {100*fids[0]}")
        if self.cfg.expt.check_f:
            print(f"gf fidelity (%): {100*fids[1]}")
            print(f"ef fidelity (%): {100*fids[2]}")
        print(f"rotation angle (deg): {angle}")
        # print(f'set angle to (deg): {-angle}')
        print(f"threshold ge: {thresholds[0]}")
        if self.cfg.expt.check_f:
            print(f"threshold gf: {thresholds[1]}")
            print(f"threshold ef: {thresholds[2]}")

    def save_data(self, data=None):
        print(f"Saving {self.fname}")
        super().save_data(data=data)
        return self.fname


# ====================================================== #


class SingleShotOptExperiment(Experiment):
    """
    Single Shot optimization experiment over readout parameters
    expt = dict(
        reps: number of shots per expt
        start_f: start frequency (MHz)
        step_f: frequency step (MHz)
        expts_f: number of experiments in frequency

        start_gain: start gain (dac units)
        step_gain: gain step (dac units)
        expts_gain: number of experiments in gain sweep

        start_len: start readout len (dac units)
        step_len: length step (dac units)
        expts_len: number of experiments in length sweep

        check_f: optimize fidelity for g/f (as opposed to g/e)
    )
    """

    def __init__(self, soccfg=None, path="", prefix="Histogram", config_file=None, progress=None):
        super().__init__(
            soccfg=soccfg,
            path=path,
            prefix=prefix,
            config_file=config_file,
            progress=progress,
        )

    def acquire(self, progress=False):
        fpts = self.cfg.expt["start_f"] + self.cfg.expt["step_f"] * np.arange(self.cfg.expt["expts_f"])
        gainpts = self.cfg.expt["start_gain"] + self.cfg.expt["step_gain"] * np.arange(self.cfg.expt["expts_gain"])
        lenpts = self.cfg.expt["start_len"] + self.cfg.expt["step_len"] * np.arange(self.cfg.expt["expts_len"])
        print(fpts)
        print(gainpts)
        print(lenpts)

        fid = np.zeros(shape=(len(fpts), len(gainpts), len(lenpts)))
        threshold = np.zeros(shape=(len(fpts), len(gainpts), len(lenpts)))
        angle = np.zeros(shape=(len(fpts), len(gainpts), len(lenpts)))

        qTest = self.cfg.expt.qTest

        for f_ind, f in enumerate(tqdm(fpts, disable=not progress)):
            for g_ind, gain in enumerate(gainpts):
                for l_ind, l in enumerate(lenpts):
                    shot = HistogramExperiment(soccfg=self.soccfg, config_file=self.config_file)
                    shot.cfg = deepcopy(self.cfg)
                    shot.cfg.device.readout.frequency[qTest] = f
                    shot.cfg.device.readout.gain[qTest] = gain
                    shot.cfg.device.readout.readout_length = l
                    check_e = True
                    if "check_f" not in self.cfg.expt:
                        check_f = False
                    else:
                        check_f = self.cfg.expt.check_f
                        check_e = not check_f
                    shot.cfg.expt = dict(
                        reps=self.cfg.expt.reps,
                        check_e=check_e,
                        check_f=check_f,
                        qTest=self.cfg.expt.qTest,
                    )
                    # print(shot.cfg)
                    shot.go(analyze=False, display=False, progress=False, save=False)
                    results = shot.analyze(verbose=False)
                    fid[f_ind, g_ind, l_ind] = results["fids"][0] if not check_f else results["fids"][1]
                    threshold[f_ind, g_ind, l_ind] = (
                        results["thresholds"][0] if not check_f else results["thresholds"][1]
                    )
                    angle[f_ind, g_ind, l_ind] = results["angle"]
                    print(f"freq: {f}, gain: {gain}, len: {l}")
                    print(f'\tfid ge [%]: {100*results["fids"][0]}')
                    if check_f:
                        print(f'\tfid gf [%]: {100*results["fids"][1]}')

        self.data = dict(
            fpts=fpts,
            gainpts=gainpts,
            lenpts=lenpts,
            fid=fid,
            threshold=threshold,
            angle=angle,
        )
        return self.data

    def analyze(self, data=None, **kwargs):
        if data == None:
            data = self.data
        fid = data["fid"]
        threshold = data["threshold"]
        angle = data["angle"]
        fpts = data["fpts"]
        gainpts = data["gainpts"]
        lenpts = data["lenpts"]

        imax = np.unravel_index(np.argmax(fid), shape=fid.shape)
        print(imax)
        print(fpts)
        print(gainpts)
        print(lenpts)
        print(f"Max fidelity {100*fid[imax]} %")
        print(
            f"Set params: \n angle (deg) {-angle[imax]} \n threshold {threshold[imax]} \n freq [Mhz] {fpts[imax[0]]} \n gain [dac units] {gainpts[imax[1]]} \n readout length [us] {lenpts[imax[2]]}"
        )

        return imax

    def display(self, data=None, **kwargs):
        if data is None:
            data = self.data

        fid = data["fid"]
        fpts = data["fpts"]  # outer sweep, index 0
        gainpts = data["gainpts"]  # middle sweep, index 1
        lenpts = data["lenpts"]  # inner sweep, index 2

        # lenpts = [data['lenpts'][0]]
        for g_ind, gain in enumerate(gainpts):
            for l_ind, l in enumerate(lenpts):
                plt.plot(
                    fpts,
                    100 * fid[:, g_ind, l_ind],
                    "o-",
                    label=f"gain: {gain:.2}, len [us]: {l}",
                )
        plt.xlabel("Frequency [MHz]")
        plt.ylabel(f"Fidelity [%]")
        plt.legend()
        plt.show()

    def save_data(self, data=None):
        print(f"Saving {self.fname}")
        super().save_data(data=data)
        return self.fname


# ====================================================== #


class MultiReadoutProgram(QutritAveragerProgram):
    def body(self):
        qTest = self.cfg.expt.qTest
        qZZ = None
        self.checkZZ = False
        if "qZZ" in self.cfg.expt and self.cfg.expt.qZZ is not None:
            qZZ = self.cfg.expt.qZZ
            self.checkZZ = True
        if qZZ is None:
            qZZ = qTest

        self.reset_and_sync()

        # initializations as necessary
        if self.checkZZ:
            self.X_pulse(q=qZZ, play=True)

        if self.cfg.expt.pulse_e:
            self.X_pulse(q=qTest, ZZ_qubit=qZZ, play=True)

        if self.cfg.expt.pulse_f:
            self.Xef_pulse(q=qTest, ZZ_qubit=qZZ, play=True)

        init_read_wait_us = self.cfg.expt.init_read_wait_us
        n_trig = self.cfg.expt.n_trig

        self.use_gf_readout = False
        if "use_gf_readout" in self.cfg.expt and self.cfg.expt.use_gf_readout:
            self.use_gf_readout = self.cfg.expt.use_gf_readout

        extended_readout_delay_cycles = 3  # delay between readout repeats for one trigger stack
        if self.use_gf_readout:
            n_trig *= 2
            self.gf_readout_init()
        for i_readout in range(self.cfg.expt.n_init_readout):
            for i_trig in range(n_trig):
                trig_offset = self.cfg.device.readout.trig_offset[0]
                # trig_offset = 0
                if i_trig == n_trig - 1:
                    syncdelay = self.us2cycles(init_read_wait_us)  # last readout for this trigger stack
                else:
                    syncdelay = (
                        extended_readout_delay_cycles  # only sync to the next readout in the same trigger stack
                    )
                    # trig_offset = 0
                print("sync delay us", self.cycles2us(syncdelay))
                # Note that by default the mux channel will play the pulse for all frequencies for the max of the pulse times on all channels - but the acquistion may not be happening the entire time.
                self.measure(
                    pulse_ch=self.measure_chs,
                    adcs=self.adc_chs,
                    adc_trig_offset=trig_offset,
                    wait=True,
                    syncdelay=syncdelay,
                )

        self.sync_all()
        self.measure(
            pulse_ch=self.measure_chs,
            adcs=self.adc_chs,
            adc_trig_offset=self.cfg.device.readout.trig_offset[0],
            wait=True,
            syncdelay=self.us2cycles(max([self.cfg.device.readout.relax_delay[q] for q in self.qubits])),
        )

    # def get_shots(self):
    #     n_init_readout = self.cfg.expt.n_init_readout
    #     n_trig = self.cfg.expt.n_trig

    #     if 'expts' not in self.cfg.expt: self.cfg.expt.expts = 1
    #     print(n_init_readout, n_trig, self.cfg.expt.reps)

    #     shots_i0 = np.array([self.di_buf[i].reshape((self.cfg.expt.expts, n_init_readout*n_trig*self.cfg.expt.reps)) / self.readout_lengths_adc[i] for i in range(len(self.ro_chs))])
    #     shots_q0 = np.array([self.dq_buf[i].reshape((self.cfg.expt.expts, n_init_readout*n_trig*self.cfg.expt.reps)) / self.readout_lengths_adc[i] for i in range(len(self.ro_chs))])

    #     shots_i0_reshaped = np.zeros((len(self.ro_chs), self.cfg.expt.expts, n_init_readout, self.cfg.expt.reps))
    #     shots_q0_reshaped = np.zeros((len(self.ro_chs), self.cfg.expt.expts, n_init_readout, self.cfg.expt.reps))
    #     for i in range(len(self.ro_chs)):
    #         for expt in range(self.cfg.expt.expts):
    #             shots_i0_reshaped[i, expt, :, :] = np.average(shots_i0[i, expt].reshape(self.cfg.expt.reps, n_init_readout, n_trig), axis=2).T
    #             shots_q0_reshaped[i, expt, :, :] = np.average(shots_q0[i, expt].reshape(self.cfg.expt.reps, n_init_readout, n_trig), axis=2).T
    #     return shots_i0_reshaped, shots_q0_reshaped


class MultiReadoutExperiment(Experiment):
    """
    Histogram Experiment
    expt = dict(
        reps: number of shots per expt
        check_e: whether to test the e state blob (true if unspecified)
        check_f: whether to also test the f state blob

        n_init_readout: number of times to do readout
        init_read_wait_us: wait time between the initialization readouts and start of next init readout/start of experiment
        n_trig: the acquisition length can't be changed within 1 experiment, so to extend the readout, repeat the standard readout length acquistiion n times
    )
    """

    def __init__(
        self,
        soccfg=None,
        path="",
        prefix="MultiReadoutHistogram",
        config_file=None,
        progress=None,
    ):
        super().__init__(
            soccfg=soccfg,
            path=path,
            prefix=prefix,
            config_file=config_file,
            progress=progress,
        )

    def acquire(self, progress=False):
        # expand entries in config that are length 1 to fill all qubits
        num_qubits_sample = len(self.cfg.device.readout.frequency)
        for subcfg in (self.cfg.device.readout, self.cfg.device.qubit, self.cfg.hw.soc):
            for key, value in subcfg.items():
                if isinstance(value, dict):
                    for key2, value2 in value.items():
                        if isinstance(value2, dict):
                            for key3, value3 in value2.items():
                                if not (isinstance(value3, list)):
                                    value2.update({key3: [value3] * num_qubits_sample})
                elif not (isinstance(value, list)):
                    subcfg.update({key: [value] * num_qubits_sample})

        data = dict()

        # self.use_gf_readout = False
        # if 'use_gf_readout' in self.cfg.expt and self.cfg.expt.use_gf_readout:
        #     self.use_gf_readout = self.cfg.expt.use_gf_readout
        # if self.use_gf_readout:
        #     self.cfg.device.readout.readout_length = 2*np.array(self.cfg.device.readout.readout_length)
        #     print('readout params', self.cfg.device.readout)
        if "avg_trigs" not in self.cfg.expt:
            self.cfg.expt.avg_trigs = True

        # ================= #
        # Baseline single shot
        # ================= #

        # Ground state shots
        cfg = AttrDict(deepcopy(self.cfg))
        cfg.expt.n_init_readout = 0
        cfg.expt.init_read_wait_us = 0
        cfg.expt.n_trig = 1
        cfg.expt.pulse_e = False
        cfg.expt.pulse_f = False
        histpro = MultiReadoutProgram(soccfg=self.soccfg, cfg=cfg)
        avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
        self.prog = histpro
        data["Ig_baseline"], data["Qg_baseline"] = histpro.get_multireadout_shots(avg_trigs=self.cfg.expt.avg_trigs)

        # Excited state shots
        if "check_e" not in self.cfg.expt:
            self.check_e = True
        else:
            self.check_e = self.cfg.expt.check_e
        if self.check_e:
            cfg = AttrDict(deepcopy(self.cfg))
            cfg.expt.n_init_readout = 0
            cfg.expt.init_read_wait_us = 0
            cfg.expt.n_trig = 1
            cfg.expt.pulse_e = True
            cfg.expt.pulse_f = False
            histpro = MultiReadoutProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["Ie_baseline"], data["Qe_baseline"] = histpro.get_multireadout_shots(
                avg_trigs=self.cfg.expt.avg_trigs
            )

        # Excited f state shots
        self.check_f = self.cfg.expt.check_f
        if self.check_f:
            cfg = AttrDict(deepcopy(self.cfg))
            cfg.expt.n_init_readout = 0
            cfg.expt.init_read_wait_us = 0
            cfg.expt.n_trig = 1
            cfg.expt.pulse_e = True
            cfg.expt.pulse_f = True
            histpro = MultiReadoutProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["If_baseline"], data["Qf_baseline"] = histpro.get_multireadout_shots(
                avg_trigs=self.cfg.expt.avg_trigs
            )

        # ================= #
        # Histograms testing different initialization readout
        # ================= #

        # Ground state shots
        cfg = AttrDict(deepcopy(self.cfg))
        cfg.expt.pulse_e = False
        cfg.expt.pulse_f = False
        histpro = MultiReadoutProgram(soccfg=self.soccfg, cfg=cfg)
        avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
        self.prog = histpro
        data["Ig"], data["Qg"] = histpro.get_multireadout_shots(avg_trigs=self.cfg.expt.avg_trigs)

        # Excited state shots
        if "check_e" not in self.cfg.expt:
            self.check_e = True
        else:
            self.check_e = self.cfg.expt.check_e
        if self.check_e:
            cfg = AttrDict(deepcopy(self.cfg))
            cfg.expt.pulse_e = True
            cfg.expt.pulse_f = False
            histpro = MultiReadoutProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["Ie"], data["Qe"] = histpro.get_multireadout_shots(avg_trigs=self.cfg.expt.avg_trigs)

        # Excited f state shots
        self.check_f = self.cfg.expt.check_f
        if self.check_f:
            cfg = AttrDict(deepcopy(self.cfg))
            cfg.expt.pulse_e = True
            # cfg.expt.pulse_e = False
            # print('WARNING TURNED OFF PULSE E FOR CHECK F')
            cfg.expt.pulse_f = True
            histpro = MultiReadoutProgram(soccfg=self.soccfg, cfg=cfg)
            avgi, avgq = histpro.acquire(self.im[self.cfg.aliases.soc], progress=progress)
            data["If"], data["Qf"] = histpro.get_multireadout_shots(avg_trigs=self.cfg.expt.avg_trigs)

        self.data = data
        return data

    def analyze(
        self,
        check_readouts,
        fit=True,
        post_select=False,
        ps_adjust=None,
        data=None,
        numbins=None,
        verbose=True,
        fitparams=None,
        plot=False,
        check_qnd=False,
        opti_post_select=False,
    ):
        if data is None:
            data = self.data

        qTest = self.cfg.expt.qTest
        num_qubits_sample = len(self.cfg.device.readout.frequency)

        # shots data shape: (len(self.ro_chs), n_init_readout + 1, self.cfg.expt.reps)
        data["iqshots"] = []
        check_states = []
        if "Ig_baseline" in data:
            data["iqshots"].append((data["Ig_baseline"][:, 0, :], data["Qg_baseline"][:, 0, :]))
            check_states.append(f"g")
            if self.cfg.expt.check_f:
                data["iqshots"].append((data["If_baseline"][:, 0, :], data["Qf_baseline"][:, 0, :]))
                check_states.append(f"f")  # indexed as 1 in data['iqshots] to match with e_states specification below
            data["iqshots"].append((data["Ie_baseline"][:, 0, :], data["Qe_baseline"][:, 0, :]))
            check_states.append(f"e")
            data["ge_avgs"] = [
                np.average(data["Ig_baseline"][qTest, 0, :]),
                np.average(data["Qg_baseline"][qTest, 0, :]),
                np.average(data["Ie_baseline"][qTest, 0, :]),
                np.average(data["Qe_baseline"][qTest, 0, :]),
            ]
            if self.cfg.expt.check_f:
                data["gf_avgs"] = [
                    np.average(data["Ig_baseline"][qTest, 0, :]),
                    np.average(data["Qg_baseline"][qTest, 0, :]),
                    np.average(data["If_baseline"][qTest, 0, :]),
                    np.average(data["Qf_baseline"][qTest, 0, :]),
                ]

        n_trig = self.cfg.expt.n_trig
        if self.cfg.expt.avg_trigs:
            n_trig = 1

        print(data.keys())
        for i_check, i_readout in enumerate(check_readouts):
            for i_trig in range(n_trig):
                if i_readout == self.cfg.expt.n_init_readout and i_trig > 0:
                    continue
                data["iqshots"].append(
                    (
                        data["Ig"][:, i_readout * n_trig + i_trig, :],
                        data["Qg"][:, i_readout * n_trig + i_trig, :],
                    )
                )
                check_states.append(f"g_{i_readout}" + (f"_{i_trig}" if n_trig > 1 else ""))

                data["iqshots"].append(
                    (
                        data["Ie"][:, i_readout * n_trig + i_trig, :],
                        data["Qe"][:, i_readout * n_trig + i_trig, :],
                    )
                )
                check_states.append(f"e_{i_readout}" + (f"_{i_trig}" if n_trig > 1 else ""))

                if self.cfg.expt.check_f:
                    data["iqshots"].append(
                        (
                            data["If"][:, i_readout * n_trig + i_trig, :],
                            data["Qf"][:, i_readout * n_trig + i_trig, :],
                        )
                    )
                    check_states.append(f"f_{i_readout}" + (f"_{i_trig}" if n_trig > 1 else ""))

        play_pulses_list = []  # this is just so we don't print play pulses in the multihist
        for check_state in check_states:
            play_pulses_list.append([0])
        g_states = [0]
        e_states = [1]

        self.check_states = check_states
        self.play_pulses_list = play_pulses_list
        self.g_states = g_states
        self.e_states = e_states

        # a1, b1, c1, a2, b2, c2:
        # a1*np.exp(-(x - b1)**2/(2*c1**2)) + a2*np.exp(-(x - b2)**2/(2*c2**2))
        # fitparams = [None, None, None, None, 150, 100]

        multihist_results = multihist(
            title=f"Single Shot Q{qTest} with Multi Readout",
            data=data,
            check_qubit=qTest,
            check_states=check_states,
            play_pulses_list=play_pulses_list,
            g_states=g_states,
            e_states=e_states,
            numbins=numbins,
            fit=fit,
            fitparams=fitparams,
            verbose=verbose,
            plot=plot,
            check_qnd=check_qnd,
        )

        if not fit:
            fids, thresholds, angle = multihist_results
        else:
            fids, thresholds, angle, popts, pcovs = multihist_results
            data["popts"] = popts
            data["pcovs"] = pcovs

            if post_select:
                # for each readout after first readout, post-select the g state preparation based on all previous measurements being in the g state
                # truth array saying whether this shot will be eliminated for the next iteration

                if ps_adjust is None:
                    ps_threshold = thresholds[0]
                else:
                    thresholds_allq = [0] * num_qubits_sample
                    thresholds_allq[qTest] = thresholds[0]
                    angles_allq = [0] * num_qubits_sample
                    angles_allq[qTest] = angle
                    ge_avgs_allq = np.zeros((num_qubits_sample, 4))
                    ge_avgs_allq[qTest] = data["ge_avgs"] if not self.cfg.expt.check_f else data["ge_avgs"]

                    if not (opti_post_select):
                        ps_threshold = ps_threshold_adjust(
                            ps_thresholds_init=thresholds_allq,
                            adjust=ps_adjust,
                            ge_avgs=ge_avgs_allq,
                            angles=angles_allq,
                        )[qTest]
                        print("ps_threshold", ps_threshold)
                        data["ps_threshold"] = ps_threshold

                        keep_prev = np.ones_like(data["Ig"][qTest, 0, :])
                        for i_readout in range(self.cfg.expt.n_init_readout + 1):
                            Ig_readout = data["Ig"][qTest, i_readout, :]
                            Qg_readout = data["Qg"][qTest, i_readout, :]
                            if i_readout > 0:
                                data[f"Ig_select{i_readout}"] = Ig_readout[keep_prev]
                                data[f"Qg_select{i_readout}"] = Qg_readout[keep_prev]
                            Ig_readout_rot, Qg_readout_rot = self.rot_iq_data(Ig_readout, Qg_readout, angle)
                            keep_prev = np.logical_and(keep_prev, Ig_readout_rot < ps_threshold)

                    else:
                        ps_adjust = [0] * num_qubits_sample
                        ps_adjust_qb = np.linspace(-2.3, 2, 20)
                        n_diff_vec = np.zeros_like(ps_adjust_qb)
                        threshold_vec = np.zeros_like(ps_adjust_qb)
                        percent_kept_vec = np.zeros_like(ps_adjust_qb)
                        n_bins = 200

                        Ig_readout_base = data["Ig"][qTest, 0, :]
                        Qg_readout_base = data["Qg"][qTest, 0, :]
                        print("angle", angle)
                        Ig_readout_rot, Qg_readout_rot = self.rot_iq_data(Ig_readout_base, Qg_readout_base, angle)
                        span = (np.max(Ig_readout_rot) - np.min(Ig_readout_rot)) / 2
                        midpoint = (np.max(Ig_readout_rot) + np.min(Ig_readout_rot)) / 2
                        xlims = [midpoint - span, midpoint + span]
                        n, bins = np.histogram(Ig_readout_base, bins=n_bins, range=xlims)
                        n_scaled = n / np.sum(n)

                        n_ps_tab = []

                        if plot:
                            x_plot = np.linspace(xlims[0], xlims[1], n_bins)
                            color_vec = plt.cm.Dark2(np.linspace(0, 1, len(ps_adjust_qb)))

                        for idx, ps in enumerate(ps_adjust_qb):

                            ps_adjust[qTest] = ps
                            ps_threshold = ps_threshold_adjust(
                                ps_thresholds_init=thresholds_allq,
                                adjust=ps_adjust,
                                ge_avgs=ge_avgs_allq,
                                angles=angles_allq,
                            )[qTest]
                            threshold_vec[idx] = ps_threshold
                            keep_prev = np.ones_like(Ig_readout_rot)

                            for i_readout in range(1, self.cfg.expt.n_init_readout + 1):

                                if idx == 0:
                                    Ig_temp = data["Ig"][qTest, i_readout, :]
                                    Qg_temp = data["Qg"][qTest, i_readout, :]
                                    Ig_temp_rot, Qg_temp_rot = self.rot_iq_data(Ig_temp, Qg_temp, angle)
                                    n_prev, bins_prev = np.histogram(Ig_temp_rot, bins=n_bins, range=xlims)
                                    n_prev_cum = np.cumsum(n_prev) / np.sum(n_prev)

                                keep_prev = np.logical_and(keep_prev, Ig_readout_rot < ps_threshold)
                                Ig_ps = Ig_temp_rot[keep_prev]
                                Qg_ps = Qg_temp_rot[keep_prev]
                                percent_kept_vec[idx] = np.sum(keep_prev) / len(keep_prev)

                                n_ps, bins_ps = np.histogram(Ig_ps, bins=n_bins, range=xlims)
                                n_ps_cum = np.cumsum(n_ps) / np.sum(n_ps)

                                n_diff = np.sum(np.abs(n_prev / np.sum(n_prev) - n_ps / np.sum(n_ps))) / 2
                                n_diff_vec[idx] += n_diff

                                n_ps_tab.append(n_ps)

                                # compute the pop bins in e or g given thresholdq

                        # print('n_diff_vec', n_diff_vec)
                        # print('percent_kept_vec', percent_kept_vec)
                        figure_of_merite = n_diff_vec * percent_kept_vec
                        idx_max = np.argmax(figure_of_merite) - 3
                        print(idx_max)
                        thres_opt = threshold_vec[idx_max]
                        print(threshold_vec)
                        print("optimal threshold", thres_opt)
                        data["ps_threshold"] = thres_opt
                        data["n_diff_opt"] = n_diff_vec[idx_max]
                        print(data["n_diff_opt"])

                        _bin = bins
                        _n_ps = n_ps_tab[idx_max]

                        # idx_bin = np.where(_bin > thresholds_allq[qTest])[0][0]
                        thresh = thresholds_allq[qTest]
                        idx_bin = np.where(_bin > thresh)[0][0]
                        n_e = np.sum(_n_ps[idx_bin:]) / np.sum(_n_ps)
                        n_g = np.sum(_n_ps[:idx_bin]) / np.sum(_n_ps)

                        n_e_prev = np.sum(n_prev[idx_bin:]) / np.sum(n_prev)
                        n_g_prev = np.sum(n_prev[:idx_bin]) / np.sum(n_prev)

                        print("n_e", n_e)
                        print("n_g", n_g)

                        print("n_e_prev", n_e_prev)
                        print("n_g_prev", n_g_prev)

                        data["n_no_ps"] = [n_g_prev, n_e_prev]
                        data["n_ps"] = [n_g, n_e]

                        if plot:

                            fig, ax = plt.subplots(1, 2, figsize=(9, 4))
                            n_ps_plot = n_ps_tab[idx_max]
                            n_ps_cum = np.cumsum(n_ps_plot) / np.sum(n_ps_plot)

                            ax[0].plot(x_plot, n_prev_cum, color="black", alpha=0.5)
                            ax[1].plot(
                                x_plot,
                                n_prev / np.sum(n_prev),
                                color="black",
                                label=f"{ps:.2f}",
                                alpha=0.5,
                            )

                            ax[0].plot(x_plot, n_ps_cum, color="black")
                            ax[1].plot(
                                x_plot,
                                n_ps_plot / np.sum(n_ps_plot),
                                color="black",
                                label=f"{ps_adjust_qb[idx_max]:.2f}",
                            )
                            ax[0].vlines(thres_opt, 0, 1, color="black", linestyle="--")
                            ax[1].vlines(
                                thres_opt,
                                0,
                                np.max(n_ps_plot / np.sum(n_ps_plot)),
                                color="black",
                                linestyle="--",
                            )
                            ax[1].vlines(
                                thresh,
                                0,
                                np.max(n_ps_plot / np.sum(n_ps_plot)),
                                color="black",
                            )

                            fig1, ax1 = plt.subplots(1, 2, figsize=(9, 4))
                            ax1[0].scatter(ps_adjust_qb, n_diff_vec * 100, color=color_vec)
                            ax1[1].scatter(ps_adjust_qb, percent_kept_vec, color=color_vec)
                            ax1[1].scatter(
                                ps_adjust_qb,
                                figure_of_merite / figure_of_merite.max(),
                                color=color_vec,
                            )
                            ax1[1].vlines(
                                ps_adjust_qb[idx_max],
                                0,
                                np.max(figure_of_merite),
                                color="black",
                                linestyle="--",
                            )
                            ax1[0].set_xlabel("PS threshold adjustment")
                            ax1[0].set_ylabel("Difference in Pop (%)")
                            ax1[1].set_xlabel("PS threshold adjustment")
                            ax1[1].set_ylabel("Percent Kept x Diff Pop")
                            fig1.tight_layout()

        return data

    def rot_iq_data(self, idata, qdata, angle):
        idata_rot = idata * np.cos(np.pi / 180 * angle) - qdata * np.sin(np.pi / 180 * angle)
        qdata_rot = idata * np.sin(np.pi / 180 * angle) + qdata * np.cos(np.pi / 180 * angle)
        return idata_rot, qdata_rot

    def display(
        self,
        fit=False,
        post_select=False,
        data=None,
        numbins=None,
        verbose=True,
        export=False,
    ):
        """
        check_readouts should be a list of integers indicating which readout indices to check; use -1 to indicate the standard (last) readout
        """
        if data is None:
            data = self.data

        qTest = self.cfg.expt.qTest
        num_qubits_sample = len(self.cfg.device.readout.frequency)

        check_states = self.check_states
        play_pulses_list = self.play_pulses_list
        if post_select:
            data = deepcopy(self.data)
            check_states = deepcopy(check_states)
            play_pulses_list = deepcopy(play_pulses_list)
            for i_readout in range(1, self.cfg.expt.n_init_readout + 1):
                Idata = data[f"Ig_select{i_readout}"]
                Qdata = data[f"Qg_select{i_readout}"]
                Idata_filled = np.zeros((num_qubits_sample, len(Idata)))
                Idata_filled[qTest] = Idata
                Qdata_filled = np.zeros((num_qubits_sample, len(Qdata)))
                Qdata_filled[qTest] = Qdata
                data["iqshots"].append((Idata_filled, Qdata_filled))
                check_states.append(f"g_s{i_readout}")
                play_pulses_list.append([0])

        ps_threshold = None
        if post_select:
            ps_threshold = data["ps_threshold"]

        multihist_results = multihist(
            title=f"Single Shot Q{qTest} with Multi Readout",
            data=data,
            check_qubit=qTest,
            check_states=check_states,
            play_pulses_list=play_pulses_list,
            g_states=self.g_states,
            e_states=self.e_states,
            numbins=numbins,
            ps_threshold=ps_threshold,
            fit=fit,
            verbose=verbose,
            plot=True,
            export=export,
        )

        if fit:
            fids, thresholds, angle, popts, pcovs = multihist_results
            for check_i, check_state in enumerate(check_states):
                a1, b1, c1, a2, b2, c2 = popts[check_i]
                a1_err, b1_err, c1_err, a2_err, b2_err, c2_err = np.sqrt(np.diag(pcovs[check_i]))
                if verbose:
                    print("check", check_state)
                    print("\tpeak 1", b1, "+/-", c1, "amplitude", a1)
                    print("\tpeak 2", b2, "+/-", c2, "amplitude", a2)

            if post_select:
                # a1, b1, c1, a2, b2, c2 = popts[0]
                i_check = check_states.index(f"g_0")
                a1, b1, c1, a2, b2, c2 = popts[i_check]
                a1_err, b1_err, c1_err, a2_err, b2_err, c2_err = np.sqrt(np.diag(pcovs[0]))
                therm_pop_err = np.sqrt((a2_err / a1) ** 2 + (a1_err * a2 / a1**2) ** 2)
                print(
                    "baseline thermal population (%)",
                    100 * a2 / a1,
                    "+/-",
                    100 * therm_pop_err,
                )

                for i_readout in range(1, self.cfg.expt.n_init_readout + 1):
                    i_check = check_states.index(f"g_s{i_readout}")
                    a1, b1, c1, a2, b2, c2 = popts[i_check]
                    a1_err, b1_err, c1_err, a2_err, b2_err, c2_err = np.sqrt(np.diag(pcovs[i_check]))
                    therm_pop_err = np.sqrt((a2_err / a1) ** 2 + (a1_err * a2 / a1**2) ** 2)
                    print(
                        f"{i_readout}th readout thermal population (%)",
                        100 * a2 / a1,
                        "+/-",
                        100 * therm_pop_err,
                    )

        if post_select and verbose:
            for i_readout in range(1, self.cfg.expt.n_init_readout + 1):
                i_check = check_states.index(f"g_s{i_readout}")
                print(
                    f"data remaining (%):",
                    100 * len(data["iqshots"][i_check][0][qTest]) / len(data["iqshots"][0][0][qTest]),
                )

    def save_data(self, data=None):
        print(f"Saving {self.fname}")
        super().save_data(data=data)
        return self.fname
