// Source: data/benchmarks/accelerating_invariant_generation/invgen/sendmail-mime-fromqp.c

int __BLAST_NONDET;

/*@
  requires outfilelen > 0;
*/
void loopy_198(int outfilelen)
{
  
  
  int nchar = 0;

  int out = 0; 

  

  while(__BLAST_NONDET)
  {
    
    if(__BLAST_NONDET)
    {
      
      if(__BLAST_NONDET)
	
	goto AFTERLOOP; 

      if(__BLAST_NONDET)
      {
	out = 0;
	nchar = 0;
	goto LOOPEND;
      }
      else
      {
	
	if(__BLAST_NONDET)  goto AFTERLOOP;

	nchar++;
	if (nchar >= outfilelen)
	  goto AFTERLOOP;

	{;
//@ assert(0<=out);
}

	{;
//@ assert(out<outfilelen);
}

	out++;
      }
    }
    else
    {
      
      nchar++;
      if (nchar >= outfilelen)
	goto AFTERLOOP;

      {;
//@ assert(0<=out);
}

      {;
//@ assert(out<outfilelen);
}

      out++;

      if(__BLAST_NONDET) goto AFTERLOOP;
    }
  LOOPEND:;
  }
 AFTERLOOP:

  {;
//@ assert(0<=out);
}

  {;
//@ assert(out<outfilelen);
}

  out++;
 RETURN:  return;
}