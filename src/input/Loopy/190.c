// Source: data/benchmarks/accelerating_invariant_generation/invgen/NetBSD_loop.c

int __BLAST_NONDET;

/*@
  requires MAXPATHLEN > 0;
*/
void loopy_190(int MAXPATHLEN, int glob2_p_off)
{
  
  
  int pathbuf_off;

  int bound_off;

  
  int glob2_pathbuf_off;
  int glob2_pathlim_off;

  

  pathbuf_off = 0;
  bound_off = pathbuf_off + (MAXPATHLEN + 1) - 1;

  glob2_pathbuf_off = pathbuf_off;
  glob2_pathlim_off = bound_off;

  {
  glob2_p_off = glob2_pathbuf_off;
  while (glob2_p_off <= glob2_pathlim_off) {
    {;
    //@ assert(0 <= glob2_p_off );
    }
     {;
    //@ assert(glob2_p_off < MAXPATHLEN + 1);
    }
    glob2_p_off++;
  }
}

 END:  return;
}