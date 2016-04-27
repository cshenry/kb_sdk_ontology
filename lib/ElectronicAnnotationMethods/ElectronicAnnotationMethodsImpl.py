#BEGIN_HEADER
# The header block is where all import statments should live
import os
import subprocess
import sys
import traceback
import uuid
from pprint import pprint, pformat
from biokbase.workspace.client import Workspace as workspaceService

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
#END_HEADER


class ElectronicAnnotationMethods:
    '''
    Module Name:
    ElectronicAnnotationMethods
    Module Description:

    '''

    ######## WARNING FOR GEVENT USERS #######
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    #########################################
    #BEGIN_CLASS_HEADER
    # Class variables and functions can be defined in this block
    workspaceURL = None

    def genome_to_protein_fasta(self, genome, fasta_file):
        records = []
        for feature in genome['features']:
            record = SeqRecord(Seq(feature['protein_translation']),
                               id=feature['id'], description=feature['function'])
            records.append(record)
        SeqIO.write(records, fasta_file, "fasta")

    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        self.workspaceURL = config['workspace-url']
        self.scratch = os.path.abspath(config['scratch'])
        if not os.path.exists(self.scratch):
            os.makedirs(self.scratch)
        #END_CONSTRUCTOR
        pass

    def interpro2go(self, ctx, params):
        # ctx is the context object
        # return variables are: output
        #BEGIN interpro2go

        # Print statements to stdout/stderr are captured and available as the method log
        print('Starting interpro2go method...')


        # Step 1 - Parse/examine the parameters and catch any errors
        # It is important to check that parameters exist and are defined, and that nice error
        # messages are returned to the user
        if 'workspace' not in params:
            raise ValueError('Parameter workspace is not set in input arguments')
        workspace_name = params['workspace']
        if 'input_genome' not in params:
            raise ValueError('Parameter input_genome is not set in input arguments')
        input_genome = params['input_genome']
        if 'output_genome' not in params:
            raise ValueError('Parameter output_genome is not set in input arguments')
        output_genome = params['output_genome']


        # Step 2- Download the input data
        # Most data will be based to your method by its workspace name.  Use the workspace to pull that data
        # (or in many cases, subsets of that data).  The user token is used to authenticate with the KBase
        # data stores and other services.  DO NOT PRINT OUT OR OTHERWISE SAVE USER TOKENS
        token = ctx['token']
        wsClient = workspaceService(self.workspaceURL, token=token)
        try:
            # Note that results from the workspace are returned in a list, and the actual data is saved
            # in the 'data' key.  So to get the ContigSet data, we get the first element of the list, and
            # look at the 'data' field.
            genome = wsClient.get_objects([{'ref': workspace_name+'/'+input_genome}])[0]['data']
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            orig_error = ''.join('    ' + line for line in lines)
            raise ValueError('Error loading input Genome object from workspace:\n' + orig_error)

        print('Got input genome data.')

        # Step 3- Actually perform the intropro2go mapping operation

        # Create feature protein FASTA
        fasta_name = 'protein.fa'
        interpro_out = 'protein.tsv'
        self.genome_to_protein_fasta(genome, fasta_name)
        # print os.popen('cat '+fasta_name).read()

        cmd = ['interproscan.sh',
               '-i', fasta_name,
               '-f', 'tsv',
               '-o', interpro_out,
               '--disable-precalc',
               '-goterms', '-iprlookup', '-hm' ]

        print('Run CMD: {}'.format(' '.join(cmd)))
        p = subprocess.Popen(cmd,
                             cwd = self.scratch, shell = False)
                             # stdout = subprocess.PIPE,
                             # stderr = subprocess.STDOUT, shell = False)

        p.wait()
        print('CMD return code: {}'.format(p.returncode))


        # good_contigs = []
        # n_total = 0;
        # n_remaining = 0;
        # for contig in contigSet['contigs']:
        #     n_total += 1
        #     if len(contig['sequence']) >= min_length:
        #         good_contigs.append(contig)
        #         n_remaining += 1

        # replace the contigs in the contigSet object in local memory
        # contigSet['contigs'] = good_contigs

        # print('Filtered ContigSet to '+str(n_remaining)+' contigs out of '+str(n_total))

        print('Here is where the ontology mapping work.')

        # Step 4- Save the new Genome back to the Workspace
        # When objects are saved, it is important to always set the Provenance of that object.  The basic
        # provenance info is given to you as part of the context object.  You can add additional information
        # to the provenance as necessary.  Here we keep a pointer to the input data object.
        provenance = [{}]
        if 'provenance' in ctx:
            provenance = ctx['provenance']
        # add additional info to provenance here, in this case the input data object reference
        provenance[0]['input_ws_objects']=[workspace_name+'/'+input_genome]

        obj_info_list = None
        try:
	        obj_info_list = wsClient.save_objects({
	                            'workspace':workspace_name,
	                            'objects': [
	                                {
	                                    'type':'KBaseGenomes.Genome',
	                                    'data':genome,
	                                    'name':output_genome,
	                                    'provenance':provenance
	                                }
	                            ]
	                        })
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            orig_error = ''.join('    ' + line for line in lines)
            raise ValueError('Error saving output Genome object to workspace:\n' + orig_error)

        info = obj_info_list[0]
        # Workspace Object Info is a tuple defined as-
        # absolute ref = info[6] + '/' + info[0] + '/' + info[4]
        # 0 - obj_id objid - integer valued ID of the object
        # 1 - obj_name name - the name of the data object
        # 2 - type_string type - the full type of the data object as: [ModuleName].[Type]-v[major_ver].[minor_ver]
        # 3 - timestamp save_date
        # 4 - int version - the object version number
        # 5 - username saved_by
        # 6 - ws_id wsid - the unique integer valued ID of the workspace containing this object
        # 7 - ws_name workspace - the workspace name
        # 8 - string chsum - md5 of the sorted json content
        # 9 - int size - size of the json content
        # 10 - usermeta meta - dictionary of string keys/values of user set or auto generated metadata

        print('Saved output Genome:'+pformat(info))


        # Step 5- Create the Report for this method, and return the results
        # Create a Report of the method
        report = 'New Genome saved to: '+str(info[7]) + '/'+str(info[1])+'/'+str(info[4])+'\n'
        # report += 'Number of initial contigs:      '+ str(n_total) + '\n'
        # report += 'Number of contigs removed:      '+ str(n_total - n_remaining) + '\n'
        # report += 'Number of contigs in final set: '+ str(n_remaining) + '\n'

        reportObj = {
            'objects_created':[{
                    'ref':str(info[6]) + '/'+str(info[0])+'/'+str(info[4]),
                    'description':'Genome with annotation mapped using interpro2go'
                }],
            'text_message':report
        }

        # generate a unique name for the Method report
        reportName = 'interpro2go_report_'+str(hex(uuid.getnode()))
        report_info_list = None
        try:
            report_info_list = wsClient.save_objects({
                    'id':info[6],
                    'objects':[
                        {
                            'type':'KBaseReport.Report',
                            'data':reportObj,
                            'name':reportName,
                            'meta':{},
                            'hidden':1, # important!  make sure the report is hidden
                            'provenance':provenance
                        }
                    ]
                })
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            orig_error = ''.join('    ' + line for line in lines)
            raise ValueError('Error saving report object to workspace:\n' + orig_error)

        report_info = report_info_list[0]

        print('Saved Report: '+pformat(report_info))

        output = {
                'report_name': reportName,
                'report_ref': str(report_info[6]) + '/' + str(report_info[0]) + '/' + str(report_info[4]),
                'output_genome_ref': str(info[6]) + '/'+str(info[0])+'/'+str(info[4])

                # TODO: add more fields
                # 'n_total_features':n_total,
                # 'n_features_mapped':n_total-n_remaining
            }

        print('Returning: '+pformat(output))

        #END interpro2go

        # At some point might do deeper type checking...
        if not isinstance(output, object):
            raise ValueError('Method interpro2go return value ' +
                             'output is not type object as required.')
        # return the results
        return [output]
