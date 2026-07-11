// Source: data/benchmarks/sv-benchmarks/loop-invgen/NetBSD_loop.c
extern int unknown_int(void);

/*@
  requires MAXPATHLEN > 0 && MAXPATHLEN < 2147483647;
*/
void loopy_366(int MAXPATHLEN, int glob2_p_off)
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