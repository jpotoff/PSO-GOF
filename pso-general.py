import numpy as np
from mpi4py import MPI
import errno
import shutil
import fileinput
import os
import sys
import datetime
import re
import xml.etree.ElementTree
import glob

comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()

class Parameter:
    def __init__(self, pars):
        self.name = pars['name']
        self.kind = pars['kind']
        self.start = float(pars['start'])
        self.end = float(pars['end'])
        self.pattern = pars['pattern']
        self.reference = pars['reference']
    
    def __str__(self):
        return '{} {} {} {} {} {}'.format(self.name, self.kind,
                                          str(self.start), str(self.end),
                                          self.pattern, self.reference)

class Parameters:
    def __init__(self, inputfile):
        self.parameters = []
        
        e = xml.etree.ElementTree.parse(inputfile).getroot()
        for par in e.find('parameters').findall('parameter'):
            pars = {}
            pars['name'] = par.find('name').text
            pars['kind'] = par.find('kind').text
            pars['start'] = par.find('start').text
            pars['end'] = par.find('end').text
            pars['pattern'] = par.find('pattern').text
            pars['reference'] = par.find('reference').text
            
            self.parameters.append(Parameter(pars))

    def GetDim(self):
        return len(self.parameters)
    
    def GetParameterByName(self, name):
        for par in self.parameters:
            if par.name == name:
                return par

class Temperature:
    def __init__(self, pars):
        self.temperature = pars['temperature']
        self.temperature_pattern = pars['temperature_pattern']
        self.molnumber_liq = pars['molnumber_liq']
        self.molnumber_liq_pattern = pars['molnumber_liq_pattern']
        self.boxsize_liq = pars['boxsize_liq']
        self.boxsize_liq_pattern = pars['boxsize_liq_pattern']
        self.eq_step = pars['eq_step']
        self.eq_step_pattern = pars['eq_step_pattern']
        self.run_step = pars['run_step']
        self.run_step_pattern = pars['run_step_pattern']
        self.pressure = pars['pressure']
        self.pressure_pattern = pars['pressure_pattern']
        self.expt_liq = pars['expt_liq']

class Temperatures:
    def __init__(self, inputfile):
        self.temperatures = []
        
        e = xml.etree.ElementTree.parse(inputfile).getroot()
        for temp in e.find('data').findall('temperature'):
            pars = {}
            pars['temperature'] = temp.find('temp').text
            pars['temperature_pattern'] = temp.find('temp').get('pattern')
            pars['molnumber_liq'] = temp.find('molnumber_liq').text
            pars['molnumber_liq_pattern'] = temp.find('molnumber_liq').get('pattern')
            pars['boxsize_liq'] = temp.find('boxsize_liq').text
            pars['boxsize_liq_pattern'] = temp.find('boxsize_liq').get('pattern')
            pars['eq_step'] = temp.find('eq_step').text
            pars['eq_step_pattern'] = temp.find('eq_step').get('pattern')
            pars['run_step'] = temp.find('run_step').text
            pars['run_step_pattern'] = temp.find('run_step').get('pattern')
            pars['pressure'] = temp.find('pressure').text
            pars['pressure_pattern'] = temp.find('pressure').get('pattern')
            pars['expt_liq'] = temp.find('expt_liq').text
                        
            self.temperatures.append(Temperature(pars))
    
    def GetDim(self):
        return len(self.temperatures)

class System:
    def __init__(self, inputfile):
        e = xml.etree.ElementTree.parse(inputfile).getroot()
        
        self.molname = e.find('system').find('molname').text
        self.molname_pattern = e.find('system').find('molname').get('pattern')
        self.resname = e.find('system').find('resname').text
        self.resname_pattern = e.find('system').find('resname').get('pattern')

class ParticleSwarmParameters:
    def __init__(self, inputfile):
        e = xml.etree.ElementTree.parse(inputfile).getroot()
        
        self.w = float(e.find('pso').find('w').text)
        self.c1 = float(e.find('pso').find('c1').text)
        self.c2 = float(e.find('pso').find('c2').text)

class Utility:
    @staticmethod
    def MakeDirectory(directory):
        os.system('mkdir -p ' + directory)
    
    @staticmethod
    def CopyDirectory(src, dest):
        os.system('cp -r ' + src + ' ' + dest)
    
    @staticmethod
    def ReplaceText(filename, text_to_search, replacement_text):
        with fileinput.FileInput(filename, inplace=True) as file:
            for line in file:
                print(line.replace(text_to_search, replacement_text), end='')
    
    @staticmethod
    def ReplaceParameters(particle, directory, tempinfo):
        temperatures = tempinfo.temperatures
        for temp in temperatures:
            for index in range(len(particle.pars)):
                parinfo = particle.parinfo.parameters
                file = directory + '/T_' + temp.temperature + '/Liq/Parameters.par'
                val = particle.pars[index]
                Utility.ReplaceText(file, parinfo[index].pattern, str(val))
                
    @staticmethod
    def ScaleContinuous(position, scale_min, scale_max):
        scale_pos = (scale_max - scale_min) * position
        scale_pos += scale_min
        return scale_pos

    @staticmethod
    def ScaleDiscrete(position, scale_min, scale_max):
        scale_pos = Utility.ScaleContinuous(position, scale_min, scale_max + 1)
        scale_pos = int(scale_pos)
        if scale_pos == scale_max + 1:
            scale_pos = scale_max
        return scale_pos

    @staticmethod
    def RunSimulation(temperatures, directory):
        loadmodule = 'module swap gnu7/7.3.0 intel/2019;'
        cd = 'cd ' + directory
        end_part = './GOMC_CPU_NPT in.conf > out.log 2>&1'
        temp = temperatures[int(rank%3)]
        folder = '/T_' + temp.temperature + '/Liq;'
        command = loadmodule + cd + folder + end_part
        os.system(command)
            
    @staticmethod
    def GetCost(particle, directory, tempinfo):
        temperatures = tempinfo.temperatures
        folders = []
        target_densities = []
        for temp in temperatures:
            folders.append('/T_' + temp.temperature + '/Liq/')
            target_densities.append(float(temp.expt_liq))
        densities = []
        for folder in folders:
            filename = directory + folder + 'Blk_PRODUCTION_BOX_0.dat'
            density = 0
            with open(filename, 'r') as file:
                lines = []
                numlines = 0
                for line in file:
                    lines.append(line)
                    numlines += 1
                if numlines < 10:
                    Utility.LogMessage('Error reading file from ' +
                                       directory + folder)
                    density = 9999
                else:
                    start_line = int(numlines * 0.8)
                    length = numlines - start_line
                    for i in range(length):
                        index = i + start_line
                        line = lines[index]
                        line = re.sub(' +', ' ', line).strip()
                        columns = line.split(' ')
                        density += float(columns[10])
                    density = density / length
            densities.append(density)
        np.copyto(particle.dens, densities)
        return Utility.CostFunction(target_densities, densities, temperatures)
    
    @staticmethod
    def CostFunction(target_densities, densities, temperatures):
        liq_coeff = 0.91
        slope_coeff = 0.09
        errors = []
        temps = []
        for i in range(len(densities)):
            error = abs(densities[i] - target_densities[i]) / target_densities[i]
            errors.append(error)
            temps.append(float(temperatures[i].temperature))
        
        sum_of_slops = 0.0
        for i in range(len(errors)-1):
            slope = (errors[i+1]-errors[i])/(temps[i+1]-temps[i])
            sum_of_slops += slope

        final = np.sum(errors) * liq_coeff + sum_of_slops * slope_coeff
        return final
    
    @staticmethod
    def GetBestParticle(swarm):
        best_particle = swarm[0]
        length = len(swarm)
        for i in range(length):
            if i % 3 == 0:
                particle = swarm[i]
                if particle.cost < best_particle.cost:
                    best_particle = particle
        return best_particle

    @staticmethod
    def LogMessage(message):
        with open('log.txt', 'a') as file:
            out = str(datetime.datetime.now()) + ' - '
            out += str(rank) + ' - '
            out += message + '\n'
            file.write(out)
            file.flush()
    
    @staticmethod
    def PrintCoordinates(it, p):
        with open('data.csv', 'a') as file:
            file.write('{},{},{},{},{},{},{}\n'
                       .format(it, p.pos, p.pars, p.dens, p.vel, p.best_pos, p.cost))
            file.flush()

    @staticmethod
    def GenerateFilesForEquilibrate(temperatures, parameters, system):
        base_directory = os.getcwd()
        shutil.rmtree('Equilibrate', ignore_errors=True)
        for temp in temperatures.temperatures:
            directory = "Equilibrate/T_" + temp.temperature + "/Liq/"
            Utility.MakeDirectory(directory)
            Utility.CopyDirectory("BUILD/model/*", directory)
            Utility.CopyDirectory("BUILD/pack/*", directory)
            Utility.CopyDirectory("BUILD/pdb/*", directory)
            os.chmod(directory + 'packmol', 509)
                
            os.chdir(directory)
            Utility.ReplaceText("pack.inp",
                                system.molname_pattern,
                                system.molname)
            Utility.ReplaceText("pack.inp", temp.molnumber_liq_pattern, 
                                temp.molnumber_liq)
            Utility.ReplaceText("pack.inp", temp.boxsize_liq_pattern,
                                temp.boxsize_liq)
            Utility.ReplaceText("build.tcl", system.resname_pattern,
                                system.resname)
                
            pars = ['epsilon', 'sigma', 'n']
            for par in pars:
                parameter = parameters.GetParameterByName(par)
                Utility.ReplaceText("Parameters.par", parameter.pattern,
                                    parameter.reference)
                
            os.system('./packmol < pack.inp' + '>> build_error.log 2>&1')
            loadmodule = 'module load vmd;'
            os.system(loadmodule + 'vmd -dispdev text < build.tcl' + '>> build_error.log 2>&1')
                
            # return to base directory
            os.chdir(base_directory)
        
    @staticmethod
    def RunEquilibrate(temperatures):
        base_directory = os.getcwd()
        
        directories = []
        temps = []
        for temp in temperatures.temperatures:
            directory = "Equilibrate/T_" + temp.temperature + "/Liq/"
            directories.append(directory)
            temps.append(temp)
        
        if rank < len(directories):
            i = rank
            directory = directories[i]
            Utility.MakeDirectory(directory)

            # Copy executable and input file from sim directory
            Utility.CopyDirectory("BUILD/sim/GOMC_CPU_NPT", directory)
            os.chmod(directory + 'GOMC_CPU_NPT', 509)
            Utility.CopyDirectory("BUILD/sim/eq.conf", directory)
            
            # Go to the simulation directory
            os.chdir(directory)
            
            # Replace parameters with values
            Utility.ReplaceText('eq.conf', temps[i].pressure_pattern,
                                temps[i].pressure)
            Utility.ReplaceText('eq.conf', temps[i].temperature_pattern,
                                temps[i].temperature)
            Utility.ReplaceText('eq.conf', temps[i].eq_step_pattern,
                                temps[i].eq_step)
            Utility.ReplaceText('eq.conf', temps[i].boxsize_liq_pattern,
                                temps[i].boxsize_liq)
            
            # Run the equilibrium simulation
            loadmodule = 'module swap gnu7/7.3.0 intel/2019;'
            os.system(loadmodule + './GOMC_CPU_NPT eq.conf &> out.log')
            
            # Go back to base directory
            os.chdir(base_directory)

    @staticmethod
    def GenerateRunFiles(directory, temperatures):
        Utility.MakeDirectory(directory)
        Utility.CopyDirectory('Equilibrate/*', directory)
        os.system('echo ' + directory +
                  '/*/*/ | xargs -n 1 cp BUILD/sim/in.conf')
        os.system('echo ' + directory +
                  '/*/*/ | xargs -n 1 cp BUILD/model/Parameters.par')
        for temp in temperatures:
            folder = directory + '/T_' + temp.temperature + '/Liq/'
            Utility.ReplaceText(folder + 'in.conf', temp.run_step_pattern,
                                temp.run_step)
            Utility.ReplaceText(folder + 'in.conf',
                                temp.temperature_pattern, temp.temperature)
            Utility.ReplaceText(folder + 'in.conf', temp.pressure_pattern,
                                temp.pressure)
            Utility.ReplaceText(folder + 'in.conf', 
                                temp.boxsize_liq_pattern, temp.boxsize_liq)

class Particle:
    def __init__(self, pars, temps):
        self.dim = pars.GetDim()
        self.tempdim = temps.GetDim()
        self.pos = np.random.uniform(0.0, 1.0, self.dim)
        self.pars = np.copy(self.pos)
        self.vel = np.zeros(shape=[self.dim], dtype=np.float32)
        self.dens = np.zeros(shape=[self.tempdim], dtype=np.float32)
        self.best_pos = np.copy(self.pos)
        self.cost = np.finfo(np.float32).max
        self.best_cost = self.cost
        self.parinfo = pars
        self.tempinfo = temps
        
    def CalculateNextVelocity(self, w, c1, c2, global_best_pos):
        self.vel = w * self.vel + c1 * np.random.uniform(0.0, 1.0, self.dim) * (self.best_pos - self.pos) + c2 * np.random.uniform(0.0, 1.0, self.dim) *                    (global_best_pos - self.pos)
        self.vel = np.minimum(self.vel, np.repeat(0.1, self.dim))
        self.vel = np.maximum(self.vel, np.repeat(-0.1, self.dim))
        
    def CalculateNextPosition(self):
        self.pos = self.pos + self.vel

        self.pos = np.minimum(self.pos, np.repeat(1.0, self.dim))
        self.pos = np.maximum(self.pos, np.repeat(0.0, self.dim))

    def UpdateBestPosition(self):
        if self.cost < self.best_cost:
            self.best_cost = self.cost
            self.best_pos = self.pos

    def ConvertPosToPars(self):
        for index in range(len(self.parinfo.parameters)):
            parameter = self.parinfo.parameters[index]
            kind = parameter.kind
            if kind == 'discrete':
                self.pars[index] = Utility.ScaleDiscrete(self.pos[index],
                                                         parameter.start,
                                                         parameter.end)
            else:
                self.pars[index] = Utility.ScaleContinuous(self.pos[index],
                                                           parameter.start,
                                                           parameter.end)

    def Evaluate(self, it):
        directory = 'runs/it{}/run{}'.format(it, int(rank/3))

        if rank % 3 == 0:
            shutil.rmtree(directory, ignore_errors=True)
            Utility.GenerateRunFiles(directory, self.tempinfo.temperatures)
            self.ConvertPosToPars()
            Utility.ReplaceParameters(self, directory, self.tempinfo)

        comm.barrier()
        Utility.RunSimulation(self.tempinfo.temperatures, directory)
        
        comm.barrier()
        if rank % 3 == 0:
            self.cost = Utility.GetCost(self, directory, self.tempinfo)

class PSO:
    def __init__(self, numIt, nPop, filename):
        it = 0
        
        # Read input file
        if rank == 0:
            self.parameters = Parameters(filename)
            self.temperatures = Temperatures(filename)
            self.system = System(filename)
            self.psoparameters = ParticleSwarmParameters(filename)
        else:
            self.parameters = None
            self.temperatures = None
            self.system = None
            self.psoparameters = None
            
        self.parameters = comm.bcast(self.parameters, root=0)
        self.temperatures = comm.bcast(self.temperatures, root=0)
        self.system = comm.bcast(self.system, root=0)
        self.psoparameters = comm.bcast(self.psoparameters, root=0)

        # Equilibrate all simulations
        if rank == 0:
            Utility.LogMessage('Generate files for equilibrium')
            Utility.GenerateFilesForEquilibrate(self.temperatures,
                                                self.parameters, self.system)
            Utility.LogMessage('Done generating equilibrium files')
            Utility.LogMessage('Running equilibrium simulations')
        comm.barrier()
        Utility.RunEquilibrate(self.temperatures)
        comm.barrier()
        if rank == 0:
            Utility.LogMessage('Done equilibrating simulations')

        # Initilize some variables
        dim = self.parameters.GetDim()
        w = self.psoparameters.w
        c1 = self.psoparameters.c1
        c2 = self.psoparameters.c2
        
        if rank == 0:
            swarm = [Particle(self.parameters, self.temperatures)
                     for i in range(nPop)]
        else:
            swarm = None
        
        if rank == 0:
            Utility.LogMessage('Scattering the initial swarm')
        particle = comm.scatter(swarm, root=0)
        
        if rank == 0:
            Utility.LogMessage('Initializing the costs for the swarm')
        particle.Evaluate(it)
        particle.UpdateBestPosition()
        comm.barrier()
        
        if rank == 0:
            Utility.LogMessage('Gathering all the costs back to node 0')
        swarm = comm.gather(particle, root=0)
        
        if rank == 0:
            length = len(swarm)
            for i in range(length):
                if i % 3 == 0:
                    p = swarm[i]
                    Utility.PrintCoordinates(it, p)
                
        if rank == 0:
            best_particle = Utility.GetBestParticle(swarm)
            Utility.LogMessage('Best global cost: {}, {}, {}, {}'
                               .format(best_particle.cost,
                                       best_particle.pars,
                                       best_particle.pos,
                                       best_particle.dens))
        it += 1
        while it <= numIt:
            if rank == 0:
                Utility.LogMessage('Starting iteration {}'.format(it))
                for i in range(len(swarm)):
                    if i % 3 == 0:
                        p = swarm[i]
                        p.CalculateNextVelocity(w, c1, c2, best_particle.pos)
                        p.CalculateNextPosition()
                
            particle = comm.scatter(swarm, root=0)
            particle.Evaluate(it)
            particle.UpdateBestPosition()
            swarm = comm.gather(particle, root=0)
        
            if rank == 0:
                length = len(swarm)
                for i in range(length):
                    if i % 3 == 0:
                        p = swarm[i]
                        Utility.PrintCoordinates(it, p)
        
            if rank == 0:
                best_p = Utility.GetBestParticle(swarm)
                if best_p.cost < best_particle.cost:
                    best_particle = best_p
                    Utility.LogMessage('Found better global cost: {}, {}, {}'
                                       .format(best_particle.cost,
                                               best_particle.pos,
                                               best_particle.dens))
                else:
                    Utility.LogMessage(
                        'Old global best is still better! {}, {}, {}'
                        .format(best_particle.cost, best_particle.pos,
                                best_particle.dens))
            it += 1

pso = PSO(30, 72, 'par.xml')
