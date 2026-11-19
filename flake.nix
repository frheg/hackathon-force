{
  description = "FORCE VibeCode hackathon: dev shells for the seismic work (inspect SEG-Y, notebooks, GPU training). The app itself still ships as Docker.";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # Python for looking at data: everything here is a prebuilt CPU package from the binary cache.
      # Training lives in .venv-gpu (see `gpu-setup`): PyTorch's own wheels carry the CUDA runtime.
      python = extra: pkgs.python3.withPackages (p: with p; [
        # SEG-Y, seismology, simulation
        segyio obspy devito pywavelets
        # arrays and tables
        numpy scipy pandas polars pyarrow duckdb xarray zarr h5py dask numba
        # images and maps
        scikit-image scikit-learn opencv4 tifffile rasterio pyproj shapely
        # plots and notebooks
        matplotlib plotly jupyterlab ipywidgets ipykernel
        # the rest
        einops tqdm pytest
      ] ++ extra p);

      cli = with pkgs; [
        uv git nodejs ruff
        # read files and bytes: a SEG-Y header is plain bytes, hexyl shows them
        hexyl xxd jq ripgrep fd bat eza visidata duckdb
        # geo rasters (SAR images, maps), video of slice fly-throughs
        gdal ffmpeg imagemagick
        # machine and downloads
        btop nvtopPackages.nvidia nvitop ncdu tmux hyperfine zstd pigz aria2
      ];

      # tools/ holds our own commands (segy, gpu-setup); they are put on PATH from the checkout, so edits apply at once
      hook = ''
        export HACKATHON_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
        export PATH="$HACKATHON_ROOT/tools:$PATH"
        echo "hackathon dev shell: segy info|text|slice|trace FILE   jupyter lab   uv run (in app/)" >&2
      '';

      shell = { extraPy ? (_: [ ]), extra ? [ ], hook' ? "", env ? { } }:
        pkgs.mkShell ({
          packages = [ (python extraPy) ] ++ cli ++ extra;
          shellHook = hook + hook';
        } // env);
    in
    {
      devShells.${system} = {
        # inspect and explore: nix develop
        default = shell { };

        # + 3D viewers: nix develop .#viz
        viz = shell { extraPy = p: [ p.pyvista p.vtk ]; extra = [ pkgs.paraview ]; };

        # training on the GPU: nix develop .#gpu, then `gpu-setup` once. The driver library lives in /run/opengl-driver
        # on NixOS, and the wheels need libstdc++ and zlib next to it.
        gpu = shell {
          env.LD_LIBRARY_PATH = "/run/opengl-driver/lib:${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib";
          hook' = ''
            if [ -f "$HACKATHON_ROOT/.venv-gpu/bin/activate" ]; then
              . "$HACKATHON_ROOT/.venv-gpu/bin/activate"
              unset PYTHONPATH  # the nix Python packages are for the other shell
              echo "gpu: .venv-gpu active" >&2
            else
              echo "gpu: run gpu-setup once to build .venv-gpu (PyTorch with CUDA 12.8 for the 5060 Ti)" >&2
            fi
          '';
        };
      };
    };
}
